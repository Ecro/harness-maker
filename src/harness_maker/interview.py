"""Interview the user (or accept defaults) to derive InterviewAnswers from a profile.

Question order:

    1. locale (free-text, default ``en``; ``en``/``ko`` ship with built-in i18n).
    2. preset (Side / Production) — recommended based on profile.
    3. dev_mode (spec-driven / task-driven) — independent of preset; default
       per preset (Side→task-driven, Production→spec-driven). Any cross OK.
    4. fused workflows + default workflow.
    5. consensus + caching (preset defaults shown).

Skills and agents are always installed in full; the `enabled` lists in the
returned answers govern default activation. Users can override per-task with
inline flags on the workflow command (documented in workflow_command.md.j2).
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

import yaml
from pydantic import ValidationError

from harness_maker.io_utils import denormalize_home_to_tilde, load_harness_yaml
from harness_maker.models import (
    _MODEL_ID_PATTERN,
    AgentModelSpec,
    AtomicStage,
    CodexAgentSpec,
    CodexSecondOpinionConfig,
    Confidence,
    DevMode,
    FeedbackConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Recommendation,
    RefFolder,
    SecondBrainConfig,
    SecondBrainFolder,
    Target,
    auto_workflow_name,
    interview_deep_gate_defaults,
)
from harness_maker.validators import validate_workflow_name

logger = logging.getLogger(__name__)

# Locales we ship i18n catalogs for; users can type any tag (free text).
_BUILTIN_LOCALES: tuple[str, ...] = ("en", "ko")
_DEFAULT_LOCALE = "en"

# Stages displayed 1-indexed in the interview.
_STAGES: list[AtomicStage] = list(AtomicStage)

# Recommended starter workflow set per preset. Users can accept (Y) or define
# custom (n).
_SIDE_STARTER: dict[str, list[AtomicStage]] = {
    "exec-rev": [AtomicStage.EXECUTE, AtomicStage.REVIEW],
    "exec-rev-wrap": [
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ],
    "exec-rev-ver-wrap": [
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.VERIFY,
        AtomicStage.WRAPUP,
    ],
    # 3-stage variant for /hm:loop per-iter use: wrapup belongs to loop-close,
    # never per-iter, so this strips wrapup vs plan-exec-rev-wrap below.
    # PLAN-loop-mid-stop-and-review-skip ADR-002.
    "plan-exec-rev": [
        AtomicStage.PLAN,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
    ],
    "plan-exec-rev-wrap": [
        AtomicStage.PLAN,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ],
}
_SIDE_DEFAULT = "exec-rev-wrap"

# Production preset deliberately OMITS plan-exec-rev-wrap (4-stage with wrapup).
# Production loop use expects plan-exec-rev (3-stage); loop-close owns wrapup
# (see loop.md.j2 step 7 + ADR-002 of PLAN-loop-mid-stop-and-review-skip).
# The 4-stage variant exists only in SIDE as a non-loop linear workflow option.
_PRODUCTION_STARTER: dict[str, list[AtomicStage]] = {
    "exec-rev": [AtomicStage.EXECUTE, AtomicStage.REVIEW],
    "exec-rev-wrap": [
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ],
    "exec-rev-ver-wrap": [
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.VERIFY,
        AtomicStage.WRAPUP,
    ],
    "exec-rev-wrap-ver": [
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
        AtomicStage.VERIFY,
    ],
    # 3-stage variant for /hm:loop per-iter use (no wrapup — owned by loop-close).
    # PLAN-loop-mid-stop-and-review-skip ADR-002.
    "plan-exec-rev": [
        AtomicStage.PLAN,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
    ],
    "res-spec-plan": [
        AtomicStage.RESEARCH,
        AtomicStage.SPEC,
        AtomicStage.PLAN,
    ],
}
_PRODUCTION_DEFAULT = "exec-rev-ver-wrap"

# Inventory of all reviewers/skills the synthesizer installs. The `enabled`
# subset depends on preset.
_ALL_REVIEWERS: list[str] = [
    "code-reviewer",
    "security-reviewer",
    "security-auditor",
    "performance-reviewer",
    "ux-reviewer",
    "concurrency-reviewer",
    "consensus-arbiter",
    "executor",
    "autoloop-coder",
]
_ALL_SKILLS: list[str] = [
    "verify-before-completion",
    "autoloop-driver",
    "ai-readiness-rubric",
    "agent-quality-rubric",
    "conditional-router",
    "worktree-isolator",
    "security-scanner",
    "context-linter",
    "refdocs-search",
]

_SIDE_ENABLED_REVIEWERS: list[str] = ["code-reviewer"]
_SIDE_ENABLED_SKILLS: list[str] = [
    "verify-before-completion",
    "autoloop-driver",
    "ai-readiness-rubric",
    "agent-quality-rubric",
    "refdocs-search",
]
_PROD_ENABLED_REVIEWERS: list[str] = [
    "code-reviewer",
    "security-reviewer",
    "performance-reviewer",
    "ux-reviewer",
    "concurrency-reviewer",
]
_PROD_ENABLED_SKILLS: list[str] = list(_ALL_SKILLS)

_FOCUS_REVIEWERS: dict[str, list[str]] = {
    "feature": ["code-reviewer", "ux-reviewer"],
    "bugfix": ["code-reviewer", "test-reviewer"],
    "security": ["code-reviewer", "security-reviewer", "security-auditor"],
    "performance": ["code-reviewer", "performance-reviewer"],
    "refactoring": ["code-reviewer", "concurrency-reviewer"],
}


def _focus_to_additional_reviewers(focus: str, preset: Preset) -> list[str]:
    """Return reviewers to enable beyond the preset default for a given work focus."""
    wanted = set(_FOCUS_REVIEWERS.get(focus, []))
    preset_defaults = set(
        _SIDE_ENABLED_REVIEWERS if preset == Preset.SIDE else _PROD_ENABLED_REVIEWERS
    )
    return sorted(wanted - preset_defaults)


def interview(
    profile: ProjectProfile,
    autoloop_mode: bool = False,
) -> InterviewAnswers:
    """Return typed answers; autoloop_mode=True takes all defaults silently."""
    recommended = _recommend_preset(profile)
    if autoloop_mode:
        return _build_answers(
            locale=_DEFAULT_LOCALE,
            targets=[Target.CLAUDE_CODE],
            preset=recommended,
            dev_mode=_recommend_dev_mode(recommended),
            fused_workflows=_starter_for(recommended),
            default_workflow=_default_for(recommended),
        )

    print(
        f"\nDetected: stack={profile.stack}, scale={profile.scale}, lifecycle={profile.lifecycle}",
    )
    locale = _ask_locale()
    targets = _ask_targets()
    preset = _ask_preset(recommended)
    dev_mode = _ask_dev_mode(preset)
    fused, default_name = _ask_fused_workflows(preset)
    consensus = _ask_with_default("consensus", _consensus_for(preset))
    caching = _ask_with_default("caching", "agent-aware")
    ref_folders = _ask_ref_folders()
    sibling_repos = _ask_sibling_repos()
    second_brain = _ask_second_brain()
    codex_second_opinion = _ask_codex_second_opinion()
    return _build_answers(
        locale=locale,
        targets=targets,
        preset=preset,
        dev_mode=dev_mode,
        fused_workflows=fused,
        default_workflow=default_name,
        consensus=consensus,
        caching=caching,
        ref_folders=ref_folders,
        sibling_repos=sibling_repos,
        second_brain=second_brain,
        codex_second_opinion=codex_second_opinion,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Locale (first question)
# ──────────────────────────────────────────────────────────────────────────────


def _ask_locale() -> str:
    """Free-text locale tag; en/ko shipped, others accepted with en fallback."""
    builtins_label = "/".join(_BUILTIN_LOCALES)
    raw = _input_or_empty(
        f"Interface language [{builtins_label} or any tag] ({_DEFAULT_LOCALE}): ",
    )
    cleaned = raw.strip()
    return cleaned or _DEFAULT_LOCALE


# ──────────────────────────────────────────────────────────────────────────────
# Targets (multi-select; preset/dev_mode 와 직교한 IDE 타깃 축)
# ──────────────────────────────────────────────────────────────────────────────


def _ask_targets() -> list[Target]:
    """IDE target multi-select. comma-separated; 빈 입력은 default [claude-code].

    PLAN-cursor-target-support.md § Targets 정책: single source 원칙으로
    ``.claude/agents/``, ``.claude/skills/``, ``.claude/hooks/`` 는 양쪽 IDE 가
    공유; cursor target 추가 시 ``.cursor/rules/``, ``.cursor/commands/``,
    ``.cursor/mcp.json`` 도 렌더.
    """
    options = ", ".join(t.value for t in Target)
    default = Target.CLAUDE_CODE.value
    raw = _input_or_empty(
        f"IDE targets [{options}] — comma-separated for multi-select ({default}): ",
    )
    cleaned = raw.strip().lower()
    if not cleaned:
        return [Target.CLAUDE_CODE]
    out: list[Target] = []
    for token in cleaned.split(","):
        s = token.strip()
        if not s:
            continue
        try:
            out.append(Target(s))
        except ValueError:
            logger.warning("unknown target %r — skipped", s)
    return out or [Target.CLAUDE_CODE]


# ──────────────────────────────────────────────────────────────────────────────
# Dev mode (independent axis; recommended per preset, any cross allowed)
# ──────────────────────────────────────────────────────────────────────────────


def _recommend_dev_mode(preset: Preset) -> DevMode:
    """Side defaults to task-driven (lighter), Production defaults to spec-driven.

    Phase 8: behavior delegated to ``recommendation.recommend_dev_mode`` so the
    registry is the single source of truth for the heuristic. Thin wrapper
    kept because callers pass a preset directly (not a full profile); we map
    preset → minimal ProjectProfile so the registry call works.
    """
    # Map preset back to the profile signals that produce it (kept in lockstep
    # with recommend_preset). If the registry recommender returns None for any
    # reason, fall back to the same heuristic locally.
    from harness_maker.recommendation import recommend_dev_mode

    proxy_profile = (
        ProjectProfile(scale="small", lifecycle="dormant")
        if preset == Preset.SIDE
        else ProjectProfile(scale="medium", lifecycle="active")
    )
    rec = recommend_dev_mode(proxy_profile, Path("."))
    if rec is None:
        return DevMode.TASK_DRIVEN if preset == Preset.SIDE else DevMode.SPEC_DRIVEN
    value = rec.value
    if not isinstance(value, DevMode):
        return DevMode.TASK_DRIVEN if preset == Preset.SIDE else DevMode.SPEC_DRIVEN
    return value


def _ask_dev_mode(preset: Preset) -> DevMode:
    recommended = _recommend_dev_mode(preset)
    other = DevMode.SPEC_DRIVEN if recommended == DevMode.TASK_DRIVEN else DevMode.TASK_DRIVEN
    label = f"dev_mode [{recommended.value} / {other.value}]"
    raw = _input_or_empty(f"{label} ({recommended.value}): ")
    cleaned = raw.strip().lower()
    if not cleaned:
        return recommended
    if cleaned.startswith(("s", "spec")):
        return DevMode.SPEC_DRIVEN
    if cleaned.startswith(("t", "task")):
        return DevMode.TASK_DRIVEN
    return recommended


# ──────────────────────────────────────────────────────────────────────────────
# Preset
# ──────────────────────────────────────────────────────────────────────────────


def _recommend_preset(profile: ProjectProfile) -> Preset:
    """Heuristic: small + experimental/maintenance → Side; else Production.

    Phase 8: behavior delegated to ``recommendation.recommend_preset`` so the
    registry is the single source of truth. Thin wrapper kept for callers
    that only need the Preset value (not the full Recommendation wrapper).
    """
    from harness_maker.recommendation import recommend_preset

    rec = recommend_preset(profile, Path("."))
    if rec is None or not isinstance(rec.value, Preset):
        # Defensive fallback — keeps legacy behaviour if registry recommender
        # is somehow unavailable.
        if profile.scale == "small" and profile.lifecycle in {"dormant", "maintenance"}:
            return Preset.SIDE
        return Preset.PRODUCTION
    return rec.value


def _ask_preset(recommended: Preset) -> Preset:
    other = Preset.PRODUCTION if recommended == Preset.SIDE else Preset.SIDE
    label = f"preset [{recommended.value} / {other.value}]"
    raw = _input_or_empty(f"{label} ({recommended.value}): ")
    if not raw:
        return recommended
    lc = raw.strip().lower()
    if lc.startswith("p"):
        return Preset.PRODUCTION
    if lc.startswith("s"):
        return Preset.SIDE
    return recommended


def _starter_for(preset: Preset) -> dict[str, list[AtomicStage]]:
    src = _SIDE_STARTER if preset == Preset.SIDE else _PRODUCTION_STARTER
    return {k: list(v) for k, v in src.items()}


def _default_for(preset: Preset) -> str:
    return _SIDE_DEFAULT if preset == Preset.SIDE else _PRODUCTION_DEFAULT


def _consensus_for(preset: Preset) -> str:
    return "single" if preset == Preset.SIDE else "cross-check"


# ──────────────────────────────────────────────────────────────────────────────
# Fused workflows
# ──────────────────────────────────────────────────────────────────────────────


def _ask_fused_workflows(
    preset: Preset,
) -> tuple[dict[str, list[AtomicStage]], str]:
    """Show stages + recommended starter; let user accept or define custom."""
    print("\nAtomic stages:")
    for i, s in enumerate(_STAGES, start=1):
        print(f"  {i}. {s.value}")

    starter = _starter_for(preset)
    print(f"\nRecommended starter set ({preset.value}):")
    for name, stages in starter.items():
        nums = ",".join(str(_STAGES.index(s) + 1) for s in stages)
        joined = ", ".join(s.value for s in stages)
        print(f"  /hm:{name}  ({nums}) → {joined}")

    use_default = _input_or_empty("Use recommended? [Y/n]: ").strip().lower()
    chosen = starter if use_default in ("", "y", "yes") else (_ask_custom_workflows() or starter)

    default_seed = _default_for(preset) if chosen is starter else next(iter(chosen))
    default_name = _ask_with_default("default workflow", default_seed)
    if default_name not in chosen:
        print(f"  (unknown workflow {default_name!r}; falling back to {default_seed})")
        default_name = default_seed
    return chosen, default_name


def _ask_custom_workflows() -> dict[str, list[AtomicStage]] | None:
    """Loop: read stage numbers + optional name override until 'done'."""
    print("\nDefine fused workflows. Type 'done' when finished.")
    custom: dict[str, list[AtomicStage]] = {}
    while True:
        idx = len(custom) + 1
        line = _input_or_empty(
            f"  Workflow #{idx} stages (e.g. 4,5,6 or 'done'): ",
        ).strip()
        if line.lower() == "done":
            if not custom:
                print("  No workflows defined; falling back to recommended set.")
                return None
            return custom
        try:
            stages = _parse_stage_numbers(line)
        except ValueError as e:
            print(f"  Invalid: {e}")
            continue
        if not stages:
            print("  No stages selected; try again.")
            continue
        suggested = auto_workflow_name(stages)
        name = _input_or_empty(f"  Name [{suggested}]: ").strip() or suggested
        try:
            validate_workflow_name(name)
        except ValueError as e:
            print(f"  {e}")
            continue
        if name in custom:
            print(f"  Name {name!r} already used; pick another.")
            continue
        custom[name] = stages


# ──────────────────────────────────────────────────────────────────────────────
# Reference document folders (multi)
# ──────────────────────────────────────────────────────────────────────────────


def _ask_ref_folders() -> list[RefFolder]:
    """Multi-line input — each line is a folder path with optional ';glob'.

    Empty input ends the loop (skip). Non-existent paths only warn — the path
    may resolve on a different machine where the harness ships, so we still
    register. DOCX files inside the folder are unsupported by the search
    skill (announced upfront, enforced at index time).
    """
    print("\nReference document folders (skill-driven search will index these).")
    print("  Format: '<path>' or '<path> ; <glob>'.  One per line.")
    print("  Default glob: **/*.{md,txt,pdf}.  DOCX is unsupported (convert first).")
    print("  Blank line to skip / finish.")
    out: list[RefFolder] = []
    while True:
        idx = len(out) + 1
        line = _input_or_empty(f"  ref_folder #{idx}: ").strip()
        if not line:
            return out
        path_part, _, glob_part = line.partition(";")
        path_part = denormalize_home_to_tilde(path_part.strip())
        glob = glob_part.strip() or "**/*.{md,txt,pdf}"
        if not path_part:
            print("  empty path; skip.")
            continue
        if not Path(path_part).expanduser().exists():
            print(f"  warn: path {path_part!r} not found on this machine (registering anyway).")
        out.append(RefFolder(path=path_part, glob=glob))


def _ask_sibling_repos() -> list[str]:
    """Collect sibling repo relative paths — one per line, blank to finish.

    Absolute paths are rejected (cross-machine portability — ADR-001).
    Missing/non-git paths only warn (portability: the path may resolve
    on a different machine where the harness ships).
    """
    print("\nSibling repos (other repos that form one logical project with this one).")
    print("  Enter relative paths (e.g. ../repo-b).  One per line.  Blank to skip/finish.")
    out: list[str] = []
    while True:
        idx = len(out) + 1
        line = _input_or_empty(f"  sibling_repo #{idx}: ").strip()
        if not line:
            return out
        if Path(line).is_absolute():
            print("  error: absolute paths are not allowed — use a relative path like ../repo-b")
            continue
        if not Path(line).exists():
            print(f"  warn: path {line!r} not found on this machine (registering anyway).")
        out.append(line)


def _ask_second_brain() -> SecondBrainConfig:
    """Ask whether to connect an Obsidian vault as Second Brain.

    Blank vault_path skips (disabled). When vault_path + project_id are both
    set, the user is also prompted for the writable-folder path so the
    rendered harness.yaml is immediately functional (ADR-003 enforcement
    at interview entry). Default suggestion: ``99_HM/{project_id}/`` (ADR-004).
    """
    print("\nObsidian Second Brain (connect a Markdown vault for stage-aware memory).")
    print("  Vault path: absolute or ~-relative path to the Obsidian vault root.")
    print("  Leave blank to skip.")
    vault_raw = _input_or_empty("  vault_path: ").strip()
    if not vault_raw:
        return SecondBrainConfig()
    vault_path = Path(vault_raw).expanduser()
    if not vault_path.exists():
        print(f"  warn: vault path {vault_raw!r} not found on this machine (registering anyway).")
    project_id_raw = _input_or_empty(
        "  project_id (kebab-case, e.g. my-app — blank to omit): "
    ).strip()
    folders: list[SecondBrainFolder] = []
    if project_id_raw:
        default_folder = f"99_HM/{project_id_raw}"
        print(
            "  Note folder (vault-relative path where harness writes durable "
            "notes — must contain project_id)."
        )
        folder_raw = _input_or_empty(f"  folder [{default_folder}]: ").strip()
        folder_path = folder_raw or default_folder
        folders = [
            SecondBrainFolder(
                path=folder_path,
                read=True,
                write=True,
            )
        ]
    return SecondBrainConfig(
        enabled=True,
        vault_path=denormalize_home_to_tilde(vault_raw),
        project_id=project_id_raw,
        folders=folders,
    )


def _parse_stage_numbers(line: str) -> list[AtomicStage]:
    out: list[AtomicStage] = []
    for tok in line.split(","):
        s = tok.strip()
        if not s:
            continue
        try:
            n = int(s)
        except ValueError as e:
            msg = f"not a number: {s!r}"
            raise ValueError(msg) from e
        if not 1 <= n <= len(_STAGES):
            msg = f"out of range (1-{len(_STAGES)}): {n}"
            raise ValueError(msg)
        out.append(_STAGES[n - 1])
    return out


def _ask_codex_second_opinion() -> CodexSecondOpinionConfig:
    """Ask whether to enable Codex CLI as a second-LLM reviewer (PLAN-codex-second-llm-integration).

    Default off (safe). When enabled, the 3 default reviewer agents
    (code-reviewer, consensus-arbiter, plan-validator) get ``Bash(codex exec:*)``
    permission + a rendered second-opinion section that invokes ``codex exec``
    hermetic-by-default (ADR-006). Requires user to have run ``codex login``.
    No follow-up sub-questions — advanced tuning happens via direct
    ``harness.yaml.codex_second_opinion.*`` edits.
    """
    print("\nCodex as second-LLM reviewer.")
    print("  When enabled, plan-validator MUST invoke `codex exec` (mandatory")
    print("  cross-model second opinion); code-reviewer / consensus-arbiter may")
    print("  invoke it (opt-in for now). Prerequisite: run `codex login` first.")
    answer = _input_or_empty("  Enable Codex second opinion? [y/N]: ").strip().lower()
    if answer in {"y", "yes"}:
        return CodexSecondOpinionConfig(enabled=True)
    return CodexSecondOpinionConfig()


# ──────────────────────────────────────────────────────────────────────────────
# Confidence-bucketed dispatch (Phase 8 — single tri-IDE dispatch site)
# ──────────────────────────────────────────────────────────────────────────────


def _dispatch_recommendation(
    rec: Recommendation,
    *,
    target: Target,  # noqa: ARG001 — kept for future slash-command embedding (validator N1).
    input_provider: Callable[[str], str] = input,
) -> Any:
    """Confidence-bucketed dispatch — single site for tri-IDE drift guard.

    ADR-004/007 contract:
      HIGH   → apply default + (caller emits yaml comment via _emit_yaml_comment)
      MEDIUM → prompt user via input_provider; return user choice or None
      LOW    → no recommendation surfaced; return None

    The ``target`` argument is reserved for future slash-command-side rendering
    (Claude Code → AskUserQuestion, Cursor → AskQuestion, Codex →
    request_user_input). The Python-side contract is target-agnostic: the
    return value is the same for the same Recommendation regardless of target
    (validator N1 — tri-IDE payload equivalence asserted in tests).
    """
    if rec.confidence == Confidence.HIGH:
        return rec.value
    if rec.confidence == Confidence.LOW:
        return None
    # MEDIUM — explicit user confirm via injected input_provider.
    label = f"{rec.axis} [{rec.value!r}] — accept? (Y/n): "
    raw = input_provider(label).strip().lower()
    return rec.value if raw in {"", "y", "yes"} else None


def _emit_yaml_comment(stream: TextIO, rec: Recommendation) -> None:
    """Emit ``# detected: <axis>=<value> (<confidence>) — <signal>`` to yaml output.

    Called by callers after a HIGH-confidence dispatch so the rendered
    harness.yaml carries a one-line trail of what was auto-applied. The
    comment is informational only — re-render does not re-read it.
    """
    confidence_str = rec.confidence.value
    line = f"# detected: {rec.axis}={rec.value!r} ({confidence_str})"
    if rec.signal:
        line += f" — {rec.signal}"
    stream.write(line + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _input_or_empty(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def _ask_with_default(label: str, default: str) -> str:
    raw = _input_or_empty(f"{label} [{default}]: ").strip()
    return raw or default


def _build_answers(
    *,
    locale: str,
    targets: list[Target],
    preset: Preset,
    dev_mode: DevMode,
    fused_workflows: dict[str, list[AtomicStage]],
    default_workflow: str,
    consensus: str | None = None,
    caching: str | None = None,
    second_brain: SecondBrainConfig | None = None,
    ref_folders: list[RefFolder] | None = None,
    sibling_repos: list[str] | None = None,
    codex_second_opinion: CodexSecondOpinionConfig | None = None,
    schema_version: int = 2,
) -> InterviewAnswers:
    is_side = preset == Preset.SIDE
    return InterviewAnswers(
        locale=locale,
        targets=list(targets),
        preset=preset,
        dev_mode=dev_mode,
        fused_workflows=fused_workflows,
        default_workflow=default_workflow,
        ref_folders=list(ref_folders) if ref_folders else [],
        sibling_repos=list(sibling_repos) if sibling_repos else [],
        second_brain=second_brain if second_brain is not None else SecondBrainConfig(),
        codex_second_opinion=(
            codex_second_opinion if codex_second_opinion is not None else CodexSecondOpinionConfig()
        ),
        reviewers={
            "installed": list(_ALL_REVIEWERS),
            "enabled": list(_SIDE_ENABLED_REVIEWERS if is_side else _PROD_ENABLED_REVIEWERS),
        },
        skills={
            "installed": list(_ALL_SKILLS),
            "enabled": list(_SIDE_ENABLED_SKILLS if is_side else _PROD_ENABLED_SKILLS),
        },
        consensus=consensus or _consensus_for(preset),
        caching=caching or "agent-aware",
        **_preset_extras(preset, schema_version=schema_version),
    )


def answers_from_harness_yaml(yaml_path: Path) -> InterviewAnswers | None:
    """Reconstruct InterviewAnswers from a previously-rendered harness.yaml.

    Used by ``/harness-maker:make`` to silently reuse a project's prior
    choices on re-render — preserving locale, dev_mode, custom workflows,
    enabled reviewers/skills, and the v0.3.0+ review-stage knobs (auto_fix /
    grade_threshold / max_review_rounds) without re-prompting the user.

    Returns None when the file is missing, the YAML is malformed, or the
    `preset` field is unparseable. The caller falls back to interactive
    interview (or `--autoloop` defaults) in that case. Schema gaps (missing
    keys from older renders) are filled with `_build_answers` defaults so
    upgrade paths from older harness-maker versions are non-fatal.
    """
    if not yaml_path.exists():
        return None
    # CLAUDE.md §2 + Phase 2 ADR: use the canonical multi-doc loader so the
    # renderer's provenance frontmatter is traversed correctly. Falling back
    # to a single-doc parse would either fail outright (multi-doc stream) or
    # silently return provenance keys as user data on truncated writes.
    try:
        data = load_harness_yaml(yaml_path)
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict) or not data:
        return None
    try:
        preset = Preset(data.get("preset", "Side"))
    except ValueError:
        return None
    try:
        dev_mode = DevMode(data.get("dev_mode", "task-driven"))
    except ValueError:
        dev_mode = DevMode.SPEC_DRIVEN if preset == Preset.PRODUCTION else DevMode.TASK_DRIVEN

    fused_workflows = _parse_workflows(data.get("workflows"), preset)
    default_workflow = _string_or(data.get("default_workflow"), next(iter(fused_workflows)))
    if default_workflow not in fused_workflows:
        default_workflow = next(iter(fused_workflows))

    targets = _parse_targets(data.get("targets"))

    sv_raw = data.get("schema_version")
    schema_version = int(sv_raw) if isinstance(sv_raw, (int, float)) else 1

    # 0.16.0 PLAN-deep-interview-question-criteria ADR-011 — warn-and-ignore for
    # deprecated deep_gate keys. The 5-term inequality gate replaces
    # max_rounds/streak_target uniformly across presets (ADR-007); these keys
    # no longer affect runtime, but we keep loading the rest of the file so
    # existing 0.15.x users upgrade without manual intervention.
    _deep_gate_raw = _dig(data, "interview", "deep_gate")
    if isinstance(_deep_gate_raw, dict):
        for _deprecated in ("max_rounds", "streak_target"):
            if _deprecated in _deep_gate_raw:
                logger.warning(
                    "harness.yaml %s: deprecated key interview.deep_gate.%s "
                    "ignored — see CHANGELOG-0.16.0 migration note (5-term "
                    "inequality gate replaces 3-layer).",
                    str(yaml_path),
                    _deprecated,
                )
    # ADR-012 kill-switch overlay: when harness.yaml has
    # interview.deep_gate.common_ground.llm_inference_enabled explicitly set,
    # apply it to the rebuilt InterviewAnswers below (after `base` is built).
    # ε / τ / inference_threshold / locale-cap are constants in code per
    # ADR-012; only this kill-switch is user-tunable. The actual overlay is
    # applied just before `return base.model_copy(...)` at the bottom — this
    # comment is the locator for that read-side hook.

    base = _build_answers(
        locale=_string_or(data.get("locale"), "en"),
        targets=targets,
        preset=preset,
        dev_mode=dev_mode,
        fused_workflows=fused_workflows,
        default_workflow=default_workflow,
        consensus=_string_or(_dig(data, "reviewers", "consensus"), None),
        caching=_string_or(data.get("caching"), None),
        schema_version=schema_version,
    )

    # Overlay user-tuned reviewer/skill enablement.
    reviewers_data = data.get("reviewers")
    if not isinstance(reviewers_data, dict):
        reviewers_data = {}
    skills_data = data.get("skills")
    if not isinstance(skills_data, dict):
        skills_data = {}
    reviewers_enabled = _list_of_strings(reviewers_data.get("enabled")) or base.reviewers["enabled"]
    skills_enabled = _list_of_strings(skills_data.get("enabled")) or base.skills["enabled"]

    # Overlay v0.3.0+ review-stage knobs when present; older harness.yaml falls
    # back to the InterviewAnswers field defaults.
    auto_fix = reviewers_data.get("auto_fix")
    grade_threshold = reviewers_data.get("grade_threshold")
    max_review_rounds = reviewers_data.get("max_review_rounds")

    domains = _list_of_strings(_dig(data, "project", "domains")) or list(base.domains)
    ref_folders = _parse_ref_folders(data.get("ref_folders"))
    second_brain = _parse_second_brain(data.get("second_brain"))
    sibling_repos = _list_of_strings(data.get("sibling_repos"))
    wrapup_docs = _list_of_strings(data.get("wrapup_docs"))

    update: dict[str, Any] = {
        "domains": domains,
        "ref_folders": ref_folders,
        "second_brain": second_brain,
        "sibling_repos": sibling_repos,
        "wrapup_docs": wrapup_docs,
        "reviewers": {
            "installed": list(base.reviewers["installed"]),
            "enabled": reviewers_enabled,
        },
        "skills": {
            "installed": list(base.skills["installed"]),
            "enabled": skills_enabled,
        },
    }
    # PLAN-auto-feedback-2026-05 ADR-002 — tolerant fallback: malformed feedback
    # section (non-dict, non-bool enabled) silently defaults to FeedbackConfig()
    # so the rest of the yaml load proceeds. CLAUDE.md checkpoint 6 reverse-mapper
    # schema-gap pattern: missing key → silent default, malformed → silent default.
    feedback_raw = data.get("feedback")
    if isinstance(feedback_raw, dict):
        feedback_enabled_raw = feedback_raw.get("enabled")
        if isinstance(feedback_enabled_raw, bool):
            # Future schema fields that fail strict validation: stay tolerant.
            with contextlib.suppress(ValidationError):
                update["feedback"] = FeedbackConfig(enabled=feedback_enabled_raw)
    # PLAN-codex-second-llm-integration — same tolerant-fallback pattern as
    # feedback: missing key OR malformed block → silent default
    # CodexSecondOpinionConfig() (enabled=False). Only the recognized fields
    # round-trip; unknown keys are ignored (forward-compat).
    csoo_raw = data.get("codex_second_opinion")
    if isinstance(csoo_raw, dict):
        # Filter to recognized keys with strict per-field validation; let
        # Pydantic do the final validation via model_validate (preserves
        # default_factory for omitted fields).
        csoo_clean: dict[str, object] = {}
        enabled_raw = csoo_raw.get("enabled")
        if isinstance(enabled_raw, bool):
            csoo_clean["enabled"] = enabled_raw
        agents_raw = csoo_raw.get("agents")
        if isinstance(agents_raw, list) and all(isinstance(a, str) for a in agents_raw):
            csoo_clean["agents"] = list(agents_raw)
        hermetic_raw = csoo_raw.get("hermetic")
        if isinstance(hermetic_raw, bool):
            csoo_clean["hermetic"] = hermetic_raw
        output_schema_raw = csoo_raw.get("output_schema_path")
        if isinstance(output_schema_raw, str):
            csoo_clean["output_schema_path"] = output_schema_raw
        with contextlib.suppress(ValidationError):
            update["codex_second_opinion"] = CodexSecondOpinionConfig.model_validate(csoo_clean)
    # ADR-002/004 silent migration: prefer the new `default_model` key; fall
    # back to the deprecated `recommended_model`. When ONLY the deprecated key
    # is present AND the file is schema_version<2, emit an advisory INFO log
    # so users discover the rename.
    #
    # Review code-reviewer P1 fix: gate on schema_version<2 — without this the
    # log fires on every fresh Phase 2 render cycle because Phase 2 templates
    # still emit `recommended_model:` (templates migrate in Phase 3, ADR-009).
    # Review security-reviewer P1 fix: sanitise newline + ESC before logging
    # to prevent log forging via crafted YAML values.
    # Review code-reviewer P1 fix: include yaml_path so users can identify
    # which file triggered the advisory across multi-repo sessions.
    # Review Phase 5 MV-1/MV-2 fix: Pydantic v2 `model_copy(update=...)` at
    # the bottom of this function bypasses `_validate_default_model_chars`.
    # Validate against the charset regex BEFORE assignment so the validator's
    # protection actually applies to the harness.yaml load path. On rejection
    # log a WARNING and fall through to the HarnessConfig default — never
    # propagate a malicious value into rendered frontmatter.
    raw_default_model = data.get("default_model")
    raw_recommended_model = data.get("recommended_model")
    if isinstance(raw_default_model, str) and raw_default_model.strip():
        cleaned = raw_default_model.strip()
        if _MODEL_ID_PATTERN.fullmatch(cleaned):
            update["default_model"] = cleaned
        else:
            safe_value = cleaned.replace("\n", "\\n").replace("\x1b", "\\x1b")
            logger.warning(
                "harness.yaml %s: `default_model: %s` rejected — value contains "
                "characters outside [a-zA-Z0-9_.:-]+ (newline / hash / quote / "
                "etc.). Falling back to harness default to prevent YAML "
                "injection into rendered agent frontmatter.",
                str(yaml_path),
                safe_value,
            )
    elif isinstance(raw_recommended_model, str) and raw_recommended_model.strip():
        cleaned = raw_recommended_model.strip()
        if _MODEL_ID_PATTERN.fullmatch(cleaned):
            update["default_model"] = cleaned
            if schema_version < 2:
                safe_value = cleaned.replace("\n", "\\n").replace("\x1b", "\\x1b")
                logger.info(
                    "harness.yaml %s: deprecated `recommended_model: %s` migrated "
                    "to `default_model` (schema v1 → v2). Preset defaults will "
                    "apply per-agent unless `agent_models:` overrides are set. "
                    "See docs/HOW-IT-WORKS.md > Agent Models.",
                    str(yaml_path),
                    safe_value,
                )
        else:
            safe_value = cleaned.replace("\n", "\\n").replace("\x1b", "\\x1b")
            logger.warning(
                "harness.yaml %s: deprecated `recommended_model: %s` rejected — "
                "value contains characters outside [a-zA-Z0-9_.:-]+. Falling "
                "back to harness default to prevent YAML injection into rendered "
                "agent frontmatter.",
                str(yaml_path),
                safe_value,
            )

    # ADR-001/002 agent_models — parse nested {claude, cursor, codex:{...}} per
    # agent name. Unknown keys (extra="forbid" via Pydantic) raise; we surface
    # as a warning and drop the whole agent override so the loader stays
    # tolerant (the renderer's Tier-2 preset map will fill in).
    raw_agent_models = data.get("agent_models")
    if isinstance(raw_agent_models, dict):
        parsed: dict[str, AgentModelSpec] = {}
        for agent_name, spec_dict in raw_agent_models.items():
            if not isinstance(agent_name, str) or not isinstance(spec_dict, dict):
                logger.warning(
                    "harness.yaml agent_models: dropping malformed entry %r "
                    "(expected dict, got %s)",
                    agent_name,
                    type(spec_dict).__name__,
                )
                continue
            try:
                # Build kwargs by pre-converting `codex` sub-dict but otherwise
                # passing through the raw user dict so AgentModelSpec's
                # extra="forbid" rejects unknown keys (not silently dropping
                # them via selective .get() — that masks typos in the user's
                # harness.yaml).
                spec_kwargs = dict(spec_dict)
                codex_spec_raw = spec_kwargs.pop("codex", None)
                if isinstance(codex_spec_raw, dict):
                    spec_kwargs["codex"] = CodexAgentSpec(**codex_spec_raw)
                elif codex_spec_raw is None:
                    spec_kwargs.pop("codex", None)
                parsed[agent_name] = AgentModelSpec(**spec_kwargs)
            except (TypeError, ValueError, ValidationError) as exc:
                # Pydantic v2 raises ValidationError (not ValueError) for
                # strict-mode type violations and extra="forbid" rejections —
                # consensus-passed P1 fix from /hm:review Round 1.
                logger.warning(
                    "harness.yaml agent_models[%s]: dropping invalid spec — %s",
                    agent_name,
                    exc,
                )
        if parsed:
            update["agent_models"] = parsed

    if isinstance(auto_fix, bool):
        update["auto_fix"] = auto_fix
    if isinstance(grade_threshold, str) and grade_threshold:
        update["grade_threshold"] = grade_threshold
    if isinstance(max_review_rounds, int):
        update["max_review_rounds"] = max_review_rounds

    # mechanical_checks — user adds shell commands manually; preserve on re-render.
    # Empty-string entries are filtered with a warning (likely typos in yaml list).
    # Old harness.yaml without the key → silent empty (valid "feature off" state).
    raw_mc = reviewers_data.get("mechanical_checks")
    if raw_mc is not None and not isinstance(raw_mc, list):
        logger.warning(
            "harness.yaml reviewers.mechanical_checks: expected a list, got %s — ignored.",
            type(raw_mc).__name__,
        )
    elif isinstance(raw_mc, list):
        clean_mc: list[str] = [c for c in raw_mc if isinstance(c, str) and c.strip()]
        dropped_mc = [repr(c) for c in raw_mc if not (isinstance(c, str) and c.strip())]
        if dropped_mc:
            logger.warning(
                "harness.yaml reviewers.mechanical_checks: dropped %d "
                "empty/non-string entries (%s).",
                len(dropped_mc),
                ", ".join(dropped_mc[:5]),
            )
        if clean_mc:
            update["mechanical_checks"] = clean_mc

    # MCP servers — user adds these manually to harness.yaml; preserve on re-render.
    # REVIEW M5/M8 (2026-05-08): validate inner dict shape (command:str, args:list[str],
    # env:dict[str,str]) and warn when entries are dropped, since the rendered
    # `.cursor/mcp.json` is executed by Cursor — silent drop on malformed yaml could
    # mask a typo that leaves the user with no MCP servers wired up.
    mcp_servers = data.get("mcp_servers")
    if isinstance(mcp_servers, dict):
        clean: dict[str, dict[str, Any]] = {}
        dropped: list[str] = []
        for k, v in mcp_servers.items():
            if not isinstance(k, str):
                dropped.append(repr(k))
                continue
            if not isinstance(v, dict):
                dropped.append(k)
                continue
            # Per-field shape validation (best-effort; unknown fields pass through
            # since MCP server spec evolves and we don't want to gate on it).
            command = v.get("command")
            args = v.get("args")
            env = v.get("env")
            if not isinstance(command, str) or not command:
                dropped.append(k)
                continue
            if args is not None and not (
                isinstance(args, list) and all(isinstance(a, str) for a in args)
            ):
                dropped.append(k)
                continue
            if env is not None and not (
                isinstance(env, dict)
                and all(isinstance(ek, str) and isinstance(ev, str) for ek, ev in env.items())
            ):
                dropped.append(k)
                continue
            clean[k] = v
        if dropped:
            logger.warning(
                "harness.yaml mcp_servers: dropped %d malformed entries (%s). "
                "Each entry must have command:str, args:list[str] (optional), "
                "env:dict[str,str] (optional). Fix the yaml or those servers will "
                "not appear in .cursor/mcp.json.",
                len(dropped),
                ", ".join(dropped[:5]),
            )
        if clean:
            update["mcp_servers"] = clean

    # ADR-012 kill-switch overlay (F6). When harness.yaml's
    # interview.deep_gate.common_ground.llm_inference_enabled is explicitly
    # set, override base.interview's default True. Other deep_gate keys are
    # code-constants per ADR-012 and ignored if present (no warning — they
    # would normally be there because we render them; we just don't read them
    # back).
    if isinstance(_deep_gate_raw, dict):
        cg_raw = _deep_gate_raw.get("common_ground")
        if isinstance(cg_raw, dict) and "llm_inference_enabled" in cg_raw:
            user_value = cg_raw["llm_inference_enabled"]
            if isinstance(user_value, bool):
                new_interview = dict(base.interview)
                new_dg = dict(new_interview.get("deep_gate", {}))
                new_cg = dict(new_dg.get("common_ground", {}))
                new_cg["llm_inference_enabled"] = user_value
                new_dg["common_ground"] = new_cg
                new_interview["deep_gate"] = new_dg
                update["interview"] = new_interview
            else:
                logger.warning(
                    "harness.yaml %s: interview.deep_gate.common_ground."
                    "llm_inference_enabled must be a boolean (got %s); "
                    "using default True.",
                    str(yaml_path),
                    type(user_value).__name__,
                )

    return base.model_copy(update=update)


def _parse_targets(raw: object) -> list[Target]:
    """yaml ``targets`` 키 파싱. 부재/잘못된 형식 시 [claude-code] fallback +
    경고 로그 (Phase 2.0 의 model 단 책임 이전 — yaml-aware loader 가 처리).
    """
    if raw is None:
        logger.warning(
            "harness.yaml has no `targets` key — falling back to [claude-code]. "
            "Re-run interview to opt into Cursor support.",
        )
        return [Target.CLAUDE_CODE]
    if not isinstance(raw, list):
        logger.warning(
            "harness.yaml `targets` is not a list — falling back to [claude-code].",
        )
        return [Target.CLAUDE_CODE]
    out: list[Target] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        try:
            out.append(Target(item))
        except ValueError:
            continue
    if not out:
        logger.warning(
            "harness.yaml `targets` had no valid entries — falling back to [claude-code].",
        )
        return [Target.CLAUDE_CODE]
    return out


def _parse_workflows(
    workflows: object,
    preset: Preset,
) -> dict[str, list[AtomicStage]]:
    """Parse the YAML ``workflows`` block into the typed shape.

    Falls back to the preset's starter set when the block is missing or
    every entry rejects validation.
    """
    fallback = dict(_SIDE_STARTER if preset == Preset.SIDE else _PRODUCTION_STARTER)
    if not isinstance(workflows, dict) or not workflows:
        return fallback
    out: dict[str, list[AtomicStage]] = {}
    for name, raw_stages in workflows.items():
        if not isinstance(name, str) or not isinstance(raw_stages, list):
            continue
        stages: list[AtomicStage] = []
        for s in raw_stages:
            if not isinstance(s, str):
                continue
            try:
                stages.append(AtomicStage(s))
            except ValueError:
                continue
        if stages:
            out[name] = stages
    return out or fallback


def _parse_ref_folders(value: object) -> list[RefFolder]:
    """Reverse-map harness.yaml ``ref_folders:`` block to typed RefFolder list.

    Tolerant of malformed entries — silently drops items missing ``path``.
    Empty/missing block returns ``[]`` (caller falls back to base default).
    """
    if not isinstance(value, list):
        return []
    out: list[RefFolder] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path:
            continue
        glob_val = item.get("glob")
        glob = glob_val if isinstance(glob_val, str) and glob_val else "**/*.{md,txt,pdf}"
        out.append(RefFolder(path=path, glob=glob))
    return out


def _parse_second_brain(value: object) -> SecondBrainConfig:
    """Reverse-map harness.yaml ``second_brain:`` block to typed config."""
    if not isinstance(value, dict):
        return SecondBrainConfig()
    try:
        return SecondBrainConfig.model_validate(value)
    except Exception as e:  # noqa: BLE001 — tolerant upgrade path like mcp_servers
        logger.warning("harness.yaml second_brain: invalid config ignored (%s).", e)
        return SecondBrainConfig()


def _string_or(value: object, fallback: str | None) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback or ""


def _list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str)]


def _dig(data: dict[str, Any], *keys: str) -> object:
    cur: object = data
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _preset_extras(preset: Preset, *, schema_version: int = 2) -> dict[str, Any]:
    """Preset-specific config defaults.

    0.16.0 (PLAN-deep-interview-question-criteria): deep_gate now uses 5-term
    inequality with uniform ε/τ across presets (ADR-007). main_loop and other
    preset-divergent fields unchanged.

    Legacy ADR-016 schema_version logic (Side v2 vs v1 differentiation) is
    retained for `main_loop.max_rounds` + `max_review_rounds` only; deep_gate
    no longer varies by schema_version.
    """
    if preset == Preset.SIDE:
        main_loop: dict[str, int | None]
        if schema_version >= 2:
            main_loop = {"max_rounds": 5}
            review_rounds = 2
        else:
            main_loop = {"max_rounds": None}
            review_rounds = 3
        return {
            "models": {"default": "sonnet"},
            "autoloop": {"allowed": False},
            "memory": {"per_repo": False},
            "anti_rot": {"enabled": False},
            "worktree": {"enabled": False},
            "security": {"gates": []},
            "context_lint": {"enabled": False},
            "interview": {
                "deep_gate": interview_deep_gate_defaults(),
                "main_loop": main_loop,
            },
            "max_review_rounds": review_rounds,
            "schema_version": schema_version,
        }
    return {
        "models": {"default": "opus", "lite": "sonnet"},
        "autoloop": {"allowed": True, "default_max_iter": 5},
        "memory": {"per_repo": True},
        "anti_rot": {"enabled": True, "sources": 4},
        "worktree": {"enabled": True},
        "security": {
            "gates": [
                "secrets",
                "permissions",
                "hook-injection",
                "cve",
                "prompt-injection",
            ],
        },
        "context_lint": {"enabled": True},
        "interview": {
            "deep_gate": interview_deep_gate_defaults(),
            "main_loop": {"max_rounds": None},
        },
        "schema_version": schema_version,
    }
