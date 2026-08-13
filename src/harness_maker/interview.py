"""Interview the user (or accept defaults) to derive InterviewAnswers from a profile.

Question order:

    1. locale (free-text, default ``en``; ``en``/``ko`` ship with built-in i18n).
    2. preset (Side / Production) — recommended based on profile.
    3. dev_mode (spec-driven / task-driven) — independent of preset; default
       per preset (Side→task-driven, Production→spec-driven). Any cross OK.
    4. worktree isolation, ref_folders, sibling_repos, Second Brain,
       cross-model second opinion, autopilot.

``consensus`` and ``caching`` are NOT asked (ADR-003 of PLAN-onboarding-interview-ux):
neither value is read by any code path or stage template, so the question was friction
with no effect. Both take their preset defaults; the fields and harness.yaml keys remain.

Skills and agents are always installed in full; the `enabled` lists in the
returned answers govern default activation. Users can override per-task with
inline flags on the stage commands.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

import yaml
from pydantic import ValidationError

from harness_maker.io_utils import denormalize_home_to_tilde, load_harness_yaml
from harness_maker.models import (
    _MODEL_ID_PATTERN,
    ASK_LEVEL,
    COMPREHENSION_DEPTHS,
    DEFAULT_COMPREHENSION_DEPTH,
    DELEGATABLE_STAGES,
    LEGACY_LEVEL_ALIASES,
    OPERATIONAL_LEVELS,
    SECOND_OPINION_MODELS,
    AgentModelSpec,
    AutonomyConfig,
    AutonomyLevel,
    CodexAgentSpec,
    Confidence,
    DelegationConfig,
    DeliveryMetricsConfig,
    DevMode,
    EconomicsConfig,
    FeedbackConfig,
    InstrumentationConfig,
    InterviewAnswers,
    PermissionsConfig,
    Preset,
    ProjectProfile,
    Recommendation,
    RefFolder,
    SecondBrainConfig,
    SecondBrainFolder,
    SecondOpinionAntigravityConfig,
    SecondOpinionConfig,
    Target,
    ToolchainConfig,
    interview_comprehension_defaults,
    interview_deep_gate_defaults,
)

logger = logging.getLogger(__name__)

# Locales we ship i18n catalogs for; users can type any tag (free text).
_BUILTIN_LOCALES: tuple[str, ...] = ("en", "ko")
_DEFAULT_LOCALE = "en"

# Stages displayed 1-indexed in the interview.

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
    # Enabled in BOTH presets, not just Production. Its §2-§4 (the cross-model gate) only
    # matter when `second_opinion.models` is non-empty, but §5 — the auto-fix loop's
    # round-state contract — governs Claude findings too, and `review.md.j2` points at it
    # from an UNGUARDED line. Omitting it from Side's enabled list would leave that pointer
    # dangling in every Side harness.
    "second-opinion-gate",
    # Same unguarded-pointer situation as `second-opinion-gate`: review.md.j2's auto-fix
    # verify step names this skill with no `{% if %}` around it, and /hm:execute Phase D
    # runs the same selector. Enabled in BOTH presets for that reason.
    "targeted-test-selection",
]

_SIDE_ENABLED_REVIEWERS: list[str] = ["code-reviewer"]
_SIDE_ENABLED_SKILLS: list[str] = [
    "verify-before-completion",
    "autoloop-driver",
    "ai-readiness-rubric",
    "agent-quality-rubric",
    "refdocs-search",
    # See the note in _ALL_SKILLS: §5 (the auto-fix round-state contract) is pointed at from
    # an unguarded line in review.md.j2, so Side must enable it too or that pointer dangles.
    "second-opinion-gate",
    # Same reason — review.md.j2's verify step points here unguarded.
    "targeted-test-selection",
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
        )

    print(
        f"\nDetected: stack={profile.stack}, scale={profile.scale}, lifecycle={profile.lifecycle}",
    )
    locale = _ask_locale()
    targets = _ask_targets()
    preset = _ask_preset(recommended)
    dev_mode = _ask_dev_mode(preset)
    worktree_enabled = _ask_worktree(preset)
    # ADR-003 of PLAN-onboarding-interview-ux: `consensus` / `caching` were asked here with
    # no explanation of their valid values, and neither changes any behaviour — nothing in
    # Python and no stage template branches on them. The fields and harness.yaml keys stay;
    # only the questions go. They now take their preset defaults.
    consensus = _consensus_for(preset)
    caching = "agent-aware"
    ref_folders = _ask_ref_folders()
    sibling_repos = _ask_sibling_repos()
    second_brain = _ask_second_brain()
    second_opinion = _ask_second_opinion()
    autonomy = _ask_autonomy()
    instrumentation = _ask_instrumentation()
    return _build_answers(
        locale=locale,
        targets=targets,
        preset=preset,
        dev_mode=dev_mode,
        consensus=consensus,
        caching=caching,
        ref_folders=ref_folders,
        sibling_repos=sibling_repos,
        second_brain=second_brain,
        second_opinion=second_opinion,
        autonomy=autonomy,
        instrumentation=instrumentation,
        worktree_enabled=worktree_enabled,
    )


def _ask_worktree(preset: Preset) -> bool:
    """PLAN-worktree-side-defaults ADR-002: the axis is now user-selectable.

    Names the cost of OFF explicitly (ADR-004) rather than leaving the user to
    discover it as a dirty working tree — that discovery is what prompted this work.
    """
    default = bool(_preset_extras(preset)["worktree"]["enabled"])
    print(
        "\nWorktree isolation — run every /hm: stage inside a per-task worktree on "
        "branch hm/<slug>?\n"
        "  on  : your working branch stays clean; /hm:wrapup squash-lands the task\n"
        "  off : simpler, but PLAN/RESEARCH/SPEC/REVIEW documents accumulate "
        "uncommitted on your current branch until wrapup commits them"
    )
    raw = _input_or_empty(f"Enable worktree isolation? [{'Y/n' if default else 'y/N'}] ")
    answer = raw.strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "true", "on"}


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


def _consensus_for(preset: Preset) -> str:
    return "single" if preset == Preset.SIDE else "cross-check"


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


def _ask_second_opinion() -> SecondOpinionConfig:
    """Ask which cross-model second-opinion CLIs to enable (PLAN-second-opinion-multi-model).

    Default off (empty ``models``). ``codex`` and ``antigravity`` are independently
    selectable (both at once is allowed). Each enabled model's reviewer agents get a
    ``Bash(<cli>:*)`` permission + a rendered second-opinion section. Prerequisites:
    ``codex login`` for codex, an authenticated ``agy`` for antigravity. When antigravity
    is selected, the model pin is resolved from a live ``agy models`` list (interview-time
    only, ADR-007) with a hardcoded fallback when ``agy`` is absent. Advanced tuning
    happens via direct ``harness.yaml.second_opinion.*`` edits.
    """
    from harness_maker.tool_detect import _BINARIES, INSTALLED_MEANS, detect_tools

    print("\nCross-model second opinion (Codex / Antigravity).")
    print("  Enabled models cast a real k-of-N consensus vote in /hm:review and are")
    print("  reconciled in /hm:plan. A missing/unauthenticated CLI degrades gracefully")
    print("  (warn + skip). Prereqs: `codex login` (codex), authenticated `agy` (antigravity).")
    found = detect_tools()
    print("  Detected on this machine:")
    for name in SECOND_OPINION_MODELS:
        state = "installed" if found.get(name, {}).get("installed") else "not installed"
        print(f"    {name:<12} ({_BINARIES[name]}) — {state}")
    print(f"  ('installed' = {INSTALLED_MEANS}.)")
    print("    1) codex    2) antigravity    3) both    4) none")
    models = _read_second_opinion_models()
    if not models:
        return SecondOpinionConfig()
    kwargs: dict[str, object] = {"models": models}
    if "antigravity" in models:
        chosen = _ask_antigravity_model()
        # Graceful-degrade (review security P2): a free-text or agy-supplied model name with
        # shell-significant chars fails _validate_model — fall back to the default rather than
        # crashing the whole interview with a ValidationError.
        try:
            kwargs["antigravity"] = SecondOpinionAntigravityConfig(model=chosen)
        except ValidationError:
            logger.warning(
                "antigravity model %r rejected (shell-significant characters) — "
                "using the default model instead.",
                chosen,
            )
            kwargs["antigravity"] = SecondOpinionAntigravityConfig()
    return SecondOpinionConfig.model_validate(kwargs)


_MAX_SECOND_OPINION_ATTEMPTS = 3

_NUMBERED_SECOND_OPINION: dict[str, list[str]] = {
    "1": ["codex"],
    "2": ["antigravity"],
    "3": ["codex", "antigravity"],
    "4": [],
}


def _read_second_opinion_models() -> list[str]:
    """Numbered choice, with the legacy comma list still accepted.

    Re-asks on an unrecognised entry instead of dropping it behind a `logger.warning` the
    user never sees — a swallowed typo is indistinguishable from declining. Bounded, so an
    unattended stdin terminates at the safe default rather than spinning.
    """
    prompt = "  Enable which models? [1-4, or a comma list like 'codex,antigravity'] (none): "
    for attempt in range(1, _MAX_SECOND_OPINION_ATTEMPTS + 1):
        raw = _input_or_empty(prompt).strip().lower()
        if not raw or raw == "none":
            return []
        if raw in _NUMBERED_SECOND_OPINION:
            return list(_NUMBERED_SECOND_OPINION[raw])
        selected = [m.strip() for m in raw.split(",") if m.strip()]
        unknown = [m for m in selected if m not in SECOND_OPINION_MODELS]
        if selected and not unknown:
            return selected
        if attempt < _MAX_SECOND_OPINION_ATTEMPTS:
            print(f"  not recognised: {', '.join(unknown) or raw!r} — pick 1-4 or a model name.")
    print("  no valid selection after 3 tries — leaving the second opinion off.")
    return []


def _ask_antigravity_model() -> str:
    """Resolve the antigravity model pin at INTERVIEW time only (ADR-007).

    Offers a live ``agy models`` list when the binary is present; falls back to the
    hardcoded default when ``agy`` is absent, times out, or errors. Render never re-shells
    (the persisted free-text value is read directly) — keeping this shell-out out of the
    render path preserves snapshot determinism.
    """
    default = SecondOpinionAntigravityConfig().model
    options = _fetch_agy_models()
    if not options:
        print(f"  (agy not available — using default model '{default}')")
        return default
    print("  Available antigravity models:")
    for i, name in enumerate(options, 1):
        print(f"    {i}. {name}")
    prompt = f"  Pick a model [1-{len(options)} or blank for '{default}']: "
    choice = _input_or_empty(prompt).strip()
    if not choice:
        return default
    with contextlib.suppress(ValueError):
        idx = int(choice)
        if 1 <= idx <= len(options):
            return options[idx - 1]
    # Free-text fallback — user typed a model name directly.
    return choice


def _fetch_agy_models() -> list[str]:
    """Live ``agy models`` list (interview-time only). Empty list on any failure (ADR-007)."""
    import shutil
    import subprocess

    if shutil.which("agy") is None:
        return []
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell, bounded timeout
            ["agy", "models"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


# ──────────────────────────────────────────────────────────────────────────────
# Autopilot / autonomy (PLAN-autopilot-config-surface — the only un-asked field surfaced)
# ──────────────────────────────────────────────────────────────────────────────


def _ask_cap(label: str) -> int | None:
    """A runaway cap: ``unlimited`` (default) → None, or a positive int.

    ADR-002: ``None`` = unlimited; a non-positive / non-numeric entry is not a valid bound,
    so it falls back to unlimited (never 0 — ``gt=0`` would reject it anyway).
    """
    raw = _input_or_empty(f"    {label} [unlimited or a number] (unlimited): ").strip().lower()
    if raw in {"", "unlimited", "none", "off"}:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _ask_instrumentation() -> InstrumentationConfig:
    """Ask whether to keep harness-maker's own development telemetry (ADR-011).

    The option text names the cost of "no" — leaving the cross-project denominator —
    because that trade has to be visible at the point of choice, not only in a PLAN. It
    is not a hypothetical: harness-maker's own six rows said "delete the plan-validator
    second pass" (0/3) while the four-project pool said keep it (2/9).
    """
    print("\nharness-maker development telemetry (stage_agent_ledger).")
    print("  Records one local row per plan-validator / test-reviewer dispatch and keeps")
    print("  each review round's finding payload, so harness-maker can tell whether its")
    print("  own gates earn their latency. 100% local — nothing is transmitted.")
    print("  Declining removes this project from that cross-project measurement, and the")
    print("  pooled population has already reversed a verdict a single project got wrong.")
    print("  A third-party install has no use for it and defaults to OFF; the maintainer's")
    print("  own projects are the ones that answer yes.")
    answer = _input_or_empty("  Turn it on? [y/N]: ").strip().lower()
    return InstrumentationConfig(stage_agent_ledger=answer in {"y", "yes"})


def _ask_autonomy() -> AutonomyConfig:
    """Ask whether to enable autopilot auto-advance + its level / persistence / caps.

    PLAN-autopilot-config-surface ADR-001/002/003. An explicit decline is pinned ``gated``;
    otherwise the offered default is ``ask`` (user decision, 2026-08-09), which defers the
    level to the session that has to live with it. ``unlimited`` is the offered cap default
    (the real safety boundary is the mandatory plan/review/wrapup gates, not the caps);
    ``autopilot_persistent`` re-arms the marker each session.
    """
    print("\nAutopilot (pipeline auto-advance).")
    print("  When enabled, /hm: stages auto-advance past two-way-door boundaries but ALWAYS")
    print("  stop at a CHANGES_REQUESTED review and at the wrapup land — no level clears those.")
    answer = _input_or_empty("  Enable autopilot auto-advance? [Y/n]: ").strip().lower()
    if answer in {"n", "no"}:
        # ADR-013: pinned, NOT a bare `AutonomyConfig()`. The class default now ASKS, so
        # inheriting it here would put the question back to a user who just answered it —
        # worse than the malformed-config case below, because here they were asked.
        return AutonomyConfig(level="gated", autopilot_persistent=False)
    print("  Levels:")
    print("    ask        — decide per session (default). The picker offers the three below")
    print("                 at the first stage of each session, so the choice is made when")
    print("                 you can see the work rather than once, months in advance.")
    print("    auto_safe  — advance the two-way doors; stop at the plan architecture")
    print("                 interview, a CHANGES_REQUESTED review, and the wrapup land.")
    print("    auto_full  — also answer the plan interview with the recommended option, and")
    print("                 an APPROVED review's human_review_needed flag. Still stops at a")
    print("                 failed grade and at the land.")
    print("    gated      — never auto-advance.")
    level_raw = _input_or_empty("  Level [ask/auto_safe/auto_full/gated] (ask): ").strip().lower()
    # An unrecognised answer takes the DEFAULT rather than erroring: this is onboarding, and a
    # typo must not arm something wider than the user asked for. `full` is the retired spelling
    # and is demoted by the alias table — mapping through it instead of spelling the levels out
    # also keeps this site clear of the enumeration guard.
    level: AutonomyLevel = LEGACY_LEVEL_ALIASES.get(level_raw, AutonomyConfig().level)
    if level_raw in OPERATIONAL_LEVELS or level_raw == ASK_LEVEL:
        level = level_raw
    persist_raw = (
        _input_or_empty("  Persist across sessions (re-arm each session)? [y/N]: ").strip().lower()
    )
    persistent = persist_raw in {"y", "yes"}
    return AutonomyConfig(
        level=level,
        step_cap=_ask_cap("step cap (chained stages)"),
        time_cap_min=_ask_cap("time cap (minutes)"),
        autopilot_persistent=persistent,
    )


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
    consensus: str | None = None,
    caching: str | None = None,
    second_brain: SecondBrainConfig | None = None,
    ref_folders: list[RefFolder] | None = None,
    sibling_repos: list[str] | None = None,
    second_opinion: SecondOpinionConfig | None = None,
    autonomy: AutonomyConfig | None = None,
    instrumentation: InstrumentationConfig | None = None,
    worktree_enabled: bool | None = None,
    toolchains: list[ToolchainConfig] | None = None,
    comprehension_depth: str | None = None,
    schema_version: int = 4,
) -> InterviewAnswers:
    is_side = preset == Preset.SIDE
    extras = _preset_extras(preset, schema_version=schema_version)
    if worktree_enabled is not None:
        extras = {**extras, "worktree": {"enabled": worktree_enabled}}
    # This rebuild takes a field ALLOWLIST, so any root field the caller does not name is
    # reset to the new preset's default. `interview` is such a field, so without this a
    # `--preset` switch silently rewrites an explicit `depth: deep` back to the default —
    # `[fail:design] promoted-default-reaches-bare-callers`, the class where the missed
    # sites are invisible to grep because they name nothing.
    if comprehension_depth is not None:
        interview = {**extras["interview"]}
        interview["comprehension"] = {"depth": comprehension_depth}
        extras = {**extras, "interview": interview}
    return InterviewAnswers(
        locale=locale,
        targets=list(targets),
        preset=preset,
        dev_mode=dev_mode,
        ref_folders=list(ref_folders) if ref_folders else [],
        sibling_repos=list(sibling_repos) if sibling_repos else [],
        second_brain=second_brain if second_brain is not None else SecondBrainConfig(),
        second_opinion=(second_opinion if second_opinion is not None else SecondOpinionConfig()),
        toolchains=list(toolchains) if toolchains else [],
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
        autonomy=autonomy if autonomy is not None else AutonomyConfig(),
        instrumentation=(
            instrumentation if instrumentation is not None else InstrumentationConfig()
        ),
        **extras,
    )


def _second_opinion_from_new_key(raw: dict[str, Any]) -> SecondOpinionConfig | None:
    """Build a SecondOpinionConfig from a modern `second_opinion` block (ADR-002 shape).

    Filters to recognized keys with per-field type guards, then defers final validation
    to Pydantic (preserving default_factory for omitted fields). Returns None on a strict
    validation failure so the caller falls back to the default.
    """
    clean: dict[str, object] = {}
    models_raw = raw.get("models")
    if isinstance(models_raw, list) and all(isinstance(m, str) for m in models_raw):
        clean["models"] = list(models_raw)
    agents_raw = raw.get("agents")
    if isinstance(agents_raw, list) and all(isinstance(a, str) for a in agents_raw):
        clean["agents"] = list(agents_raw)
    # failure_policy is a single-value Literal today, but round-trip it so the reverse-mapper
    # stays complete if the Literal ever grows (review P3).
    fp_raw = raw.get("failure_policy")
    if isinstance(fp_raw, str):
        clean["failure_policy"] = fp_raw
    for sub_key in ("codex", "antigravity"):
        sub_raw = raw.get(sub_key)
        if isinstance(sub_raw, dict):
            # Sub-block validation happens inside SecondOpinionConfig.model_validate.
            clean[sub_key] = dict(sub_raw)
    try:
        return SecondOpinionConfig.model_validate(clean)
    except ValidationError:
        return None


def _second_opinion_from_legacy(raw: dict[str, Any]) -> SecondOpinionConfig | None:
    """Migrate a legacy single-vendor `codex_second_opinion` block (ADR-001).

    `enabled: true` → models=["codex"], carrying hermetic/output_schema_path into the
    codex sub-block; `enabled: false`/absent → models=[]. Malformed → None (default).
    """
    enabled = raw.get("enabled")
    models = ["codex"] if enabled is True else []
    codex_kwargs: dict[str, object] = {}
    hermetic_raw = raw.get("hermetic")
    if isinstance(hermetic_raw, bool):
        codex_kwargs["hermetic"] = hermetic_raw
    # The legacy default output_schema_path pointed at the old filename; drop it on
    # migration so the new default (renamed schema file) is used — a stale legacy path
    # would point at a file the renderer no longer produces.
    agents_raw = raw.get("agents")
    kwargs: dict[str, object] = {"models": models}
    if isinstance(agents_raw, list) and all(isinstance(a, str) for a in agents_raw):
        kwargs["agents"] = list(agents_raw)
    if codex_kwargs:
        kwargs["codex"] = codex_kwargs
    try:
        return SecondOpinionConfig.model_validate(kwargs)
    except ValidationError:
        return None


def _load_second_opinion(data: dict[str, Any]) -> SecondOpinionConfig | None:
    """Precedence-aware second-opinion load (ADR-001).

    New `second_opinion` key wins; a legacy `codex_second_opinion` block is used only when
    the new key is absent. Both-present (or a stale legacy key at schema_version>=3) logs one
    advisory and ignores the legacy block. Returns None when neither key is present (caller
    keeps the default_factory).
    """
    new_raw = data.get("second_opinion")
    legacy_raw = data.get("codex_second_opinion")
    if isinstance(new_raw, dict):
        if isinstance(legacy_raw, dict):
            logger.info(
                "harness.yaml has both 'second_opinion' and legacy 'codex_second_opinion' — "
                "using 'second_opinion'; the legacy key is ignored (re-render to drop it)."
            )
        return _second_opinion_from_new_key(new_raw)
    if isinstance(legacy_raw, dict):
        logger.info(
            "harness.yaml 'codex_second_opinion' is deprecated → migrated to 'second_opinion' "
            "(re-render via /harness-maker:make to persist the new shape)."
        )
        return _second_opinion_from_legacy(legacy_raw)
    return None


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
        # ADR-002: an ABSENT dev_mode key resolves to task-driven (relaxed) — the
        # intentional asymmetry vs the models.py default (SPEC_DRIVEN for bare
        # construction). A config that lost its key must never surprise-force SPEC.
        dev_mode = DevMode(data.get("dev_mode", "task-driven"))
    except ValueError:
        dev_mode = DevMode.SPEC_DRIVEN if preset == Preset.PRODUCTION else DevMode.TASK_DRIVEN

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
    # Round-trip the deny-list opt-out so /hm:make --update preserves a user's
    # `permissions.deny_dangerous: true` (REVIEW P1 — was dropped at this step).
    perms_data = data.get("permissions")
    permissions = (
        PermissionsConfig(deny_dangerous=bool(perms_data.get("deny_dangerous", False)))
        if isinstance(perms_data, dict)
        else PermissionsConfig()
    )

    # Round-trip the on-disk `worktree` block (PLAN-worktree-side-defaults ADR-001).
    # Without this, `worktree` is rebuilt from `_preset_extras` and synthesize
    # overwrites the file's block on every re-render, clobbering an explicit opt-out
    # — the V3 defect, in its original `scope` form.
    #
    # The block is NORMALIZED to the single live key here rather than merged: the
    # retired `scope`/`branch_prefix` must not survive into a re-render, and the
    # legacy generations are resolved by the SAME function the runtime reader uses
    # (`worktree.resolve_worktree_enabled`) so the two can never disagree about the
    # same on-disk bytes. `None` (nothing present) keeps the preset default; the
    # make-time migration owns the louder handling of that case.
    from harness_maker.worktree import resolve_worktree_enabled

    disk_worktree = data.get("worktree")
    disk_worktree = disk_worktree if isinstance(disk_worktree, dict) else {}
    _res = resolve_worktree_enabled(disk_worktree)
    if _res.diagnostic:
        # Surface it: the re-render OVERWRITES the offending value, so a silent
        # resolution destroys a hand-edit and never says why.
        print(f"[worktree] {_res.diagnostic}", file=sys.stderr)
    merged_worktree: dict[str, Any] = {
        "enabled": bool(base.worktree.get("enabled")) if _res.value is None else _res.value
    }

    update: dict[str, Any] = {
        "worktree": merged_worktree,
        "domains": domains,
        "ref_folders": ref_folders,
        "second_brain": second_brain,
        "permissions": permissions,
        "autonomy": _parse_autonomy(data.get("autonomy")),
        "instrumentation": _parse_instrumentation(data.get("instrumentation")),
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
    # PLAN-second-opinion-multi-model ADR-001 — precedence-aware load with one-time
    # legacy migration. The NEW `second_opinion` key always wins; a legacy
    # `codex_second_opinion` block is read only when `second_opinion` is absent, and
    # its presence alongside (or after) the new key produces one advisory log line.
    so_result = _load_second_opinion(data)
    if so_result is not None:
        update["second_opinion"] = so_result
    # PLAN-cfr-churn-metrics ADR-003 — same tolerant-fallback pattern as
    # feedback/second_opinion: missing key OR malformed block → silent
    # default DeliveryMetricsConfig() (enabled=False). Recognized keys are
    # filtered so unknown/forward-compat keys don't poison the whole load;
    # a strict-invalid value (e.g. enabled: "yes") falls back to defaults.
    dm_raw = data.get("delivery_metrics")
    if isinstance(dm_raw, dict):
        dm_clean = {k: v for k, v in dm_raw.items() if k in DeliveryMetricsConfig.model_fields}
        with contextlib.suppress(ValidationError):
            update["delivery_metrics"] = DeliveryMetricsConfig.model_validate(dm_clean)
    # PLAN-harness-economics-observability — identical tolerant-fallback shape: an
    # absent or malformed block yields a default EconomicsConfig() rather than
    # poisoning the whole load (checkpoint 6, bidirectional mapper).
    econ_raw = data.get("economics")
    if isinstance(econ_raw, dict):
        econ_clean = {k: v for k, v in econ_raw.items() if k in EconomicsConfig.model_fields}
        with contextlib.suppress(ValidationError):
            update["economics"] = EconomicsConfig.model_validate(econ_clean)
    # PLAN-economics-attribution-and-carry ADR-011 — same tolerant-fallback shape. This
    # key is the ROLLBACK switch for delegation, so losing it here would leave a user
    # whose wrapup quality degraded with no way back short of a patch release.
    deleg_raw = data.get("delegation")
    if isinstance(deleg_raw, dict):
        deleg_clean = {k: v for k, v in deleg_raw.items() if k in DelegationConfig.model_fields}
        with contextlib.suppress(ValidationError):
            delegation = DelegationConfig.model_validate(deleg_clean)
            update["delegation"] = delegation
            if delegation.unknown_stages:
                # A typo is not an error — it is an opt-in that never fires. Say so
                # once rather than letting it read as "delegation is on".
                logger.warning(
                    "harness.yaml delegation.stages contains unrecognised name(s) %s — "
                    "they will never match a stage (known: %s)",
                    ", ".join(sorted(delegation.unknown_stages)),
                    ", ".join(DELEGATABLE_STAGES),
                )
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

    # toolchains — root-level (ADR-002). User-maintained OR make-time-seeded; either way it
    # must survive re-render, same contract as mechanical_checks above. Absent key → empty
    # list, which the oracle reads as "fall back to the historical Python triple for .py
    # paths and emit no oracle for anything else" (ADR-006). A malformed value is dropped
    # LOUDLY rather than silently: a silent drop reads identically to "not configured", and
    # the whole point of this key is that the not-configured state is now visible.
    raw_tc = data.get("toolchains")
    if raw_tc is not None and not isinstance(raw_tc, list):
        logger.warning(
            "harness.yaml toolchains: expected a list, got %s — ignored.",
            type(raw_tc).__name__,
        )
    elif isinstance(raw_tc, list) and raw_tc:
        try:
            update["toolchains"] = [ToolchainConfig.model_validate(e) for e in raw_tc]
        except Exception as exc:  # noqa: BLE001 — any shape error degrades to "unconfigured"
            logger.warning("harness.yaml toolchains: unusable (%s) — ignored.", exc)

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

    # PLAN-plan-interview-comprehension ADR-002: the SECOND read-side overlay.
    #
    # `_preset_extras` rebuilds the whole `interview` block, so a key added there alone is
    # silently reset to the preset default on every `--update` — the failure mode that
    # reverted hand-edited `scope`/`branch_prefix` before 0.48.0. ADR-012 froze eps/tau/cap
    # as code constants, which is exactly why there is no generic round-trip to inherit.
    #
    # A THIRD addition here should become a generic mechanism instead of a third hand-wired
    # overlay.
    _comprehension_raw = _dig(data, "interview", "comprehension")
    new_interview = dict(update.get("interview", base.interview))
    new_interview["comprehension"] = _parse_comprehension(_comprehension_raw, yaml_path)
    update["interview"] = new_interview

    return base.model_copy(update=update)


def _parse_comprehension(raw: object, yaml_path: object) -> dict[str, Any]:
    """Resolve ``interview.comprehension`` — fail-open, never raising (ADR-004/006).

    Absent, malformed, or unknown all land on the default. ADR-006 makes that an accepted
    retrofit rather than a preservation bug: an existing harness gains the disclosure on
    its next re-render and opts back out with ``depth: minimal``.

    Fail-OPEN rather than fail-closed on purpose. Falling back to ``minimal`` would let one
    typo silently disable the feature, which is this repo's most-recurring failure class
    (absent-case = feature black hole, count:8). Raising would be worse still — no other
    key in ``harness.yaml`` kills the load.
    """
    resolved = interview_comprehension_defaults()
    if raw is None:
        return resolved
    if not isinstance(raw, dict):
        logger.warning(
            "harness.yaml %s: interview.comprehension must be a mapping (got %s); "
            "using depth: %s. The value will be rewritten on the next re-render.",
            str(yaml_path),
            type(raw).__name__,
            DEFAULT_COMPREHENSION_DEPTH,
        )
        return resolved
    if "depth" not in raw:
        return resolved
    depth = raw["depth"]
    if isinstance(depth, str) and depth in COMPREHENSION_DEPTHS:
        resolved["depth"] = depth
        return resolved
    # The warning is the ONLY notice the user ever gets: normalization happens here, the
    # harness-yaml emitters re-emit from the normalized config, so the typo is overwritten
    # on the next `--update` and this branch can never be reached again. Say so.
    logger.warning(
        "harness.yaml %s: interview.comprehension.depth %r is not one of %s; "
        "using depth: %s. The invalid value will be overwritten (rewritten) in "
        "harness.yaml on the next re-render, so this warning fires only once.",
        str(yaml_path),
        depth,
        ", ".join(COMPREHENSION_DEPTHS),
        DEFAULT_COMPREHENSION_DEPTH,
    )
    return resolved


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


def _parse_instrumentation(value: object) -> InstrumentationConfig:
    """Absent block → ON, said out loud once (ADR-011).

    The maintainer-preserving direction is the OPPOSITE of the autonomy block above.
    There, an absent block must not silently escalate a user's autonomy. Here, an absent
    block must not silently STOP a project that is already contributing ledger rows — a
    re-render that quietly emptied the cross-project denominator is the failure this
    default exists to prevent, and that denominator has already reversed one verdict.
    """
    if not isinstance(value, dict):
        logger.info(
            "harness.yaml has no `instrumentation:` block — keeping harness-maker's "
            "stage_agent_ledger rows ON (a re-render must not silently stop a project "
            "from contributing). Opt out with `instrumentation.stage_agent_ledger: false`."
        )
        return InstrumentationConfig(stage_agent_ledger=True)
    raw = value.get("stage_agent_ledger")
    if not isinstance(raw, bool):
        if raw is not None:
            logger.warning(
                "harness.yaml instrumentation: non-bool stage_agent_ledger ignored → true."
            )
        return InstrumentationConfig(stage_agent_ledger=True)
    return InstrumentationConfig(stage_agent_ledger=raw)


def _parse_autonomy(value: object) -> AutonomyConfig:
    """Reverse-map harness.yaml ``autonomy:`` block to typed config.

    Tolerant like ``_parse_second_brain``: a missing OR malformed block (bad enum,
    wrong types) falls back to the default ``gated`` config so an old or hand-edited
    harness.yaml never breaks the load (ADR-002 absent-case = gated). ``strict=False``
    lets yaml stage strings coerce into ``AtomicStage`` for the pipeline list while
    the ``level`` Literal still rejects unknown values (→ caught → gated fallback).
    """
    if not isinstance(value, dict):
        # ADR-013: pinned gated. A harness.yaml with no `autonomy:` block must not be
        # escalated by a package upgrade alone; the promoted default reaches users through
        # a re-render (`/harness-maker:make --update`), never through a silent load.
        return AutonomyConfig(level="gated", autopilot_persistent=False)
    # `strict=False` is needed for the yaml stage strings → AtomicStage pipeline coercion, but
    # it would ALSO coerce a hand-edited non-bool `autopilot_persistent` ("true" / "yes" / 1)
    # into a real bool — which the autoarm hook's strict `is True` check was designed to reject,
    # silently enabling persistent autoarm on the next re-render. Drop a non-bool so it falls to
    # the safe default (False), mirroring the worktree.feature_branch_workflow strictness
    # contract [[two-readers-of-one-config-must-agree-on-strictness]] (Codex review P2).
    if "autopilot_persistent" in value and not isinstance(value["autopilot_persistent"], bool):
        logger.warning("harness.yaml autonomy: non-bool autopilot_persistent ignored → false.")
        # Pin False rather than DELETING the key. Deletion used to be equivalent because the
        # class default was False; ADR-010 flipped it to True, which turned this guard inside
        # out — a hand-edited `autopilot_persistent: "true"` would have silently enabled the
        # persistent auto-arm this branch exists to reject. (Fifth conservative site; the
        # PLAN named four. Caught by test_autopilot_review_fixes, not by review.)
        value = {**value, "autopilot_persistent": False}
    # `guard_when` was RETIRED (the autopilot_guard hook + its interactive-scope axis were
    # removed). An existing harness.yaml still carries the key, but AutonomyConfig now forbids
    # extras — drop it here so model_validate does not reject the WHOLE block and silently reset
    # the user's level / caps / pipeline to defaults on re-render (retired-key migration).
    if "guard_when" in value:
        value = {k: val for k, val in value.items() if k != "guard_when"}
    raw_level = value.get("level")
    if isinstance(raw_level, str) and raw_level in LEGACY_LEVEL_ALIASES:
        # The `--update` advisory. The re-render WRITES the new spelling, so without a line
        # here the user's committed value changes under them with no notice — and `full` is
        # the one value whose new name (`auto_full`) means something different from what it
        # migrates to (`auto_safe`), which is exactly the confusion worth pre-empting.
        logger.warning(
            "harness.yaml autonomy.level: %r is the pre-0.51 name for %r and is being "
            "migrated to it — NOT to the widest of the operational levels (%s), which is a "
            "policy you have not opted into. Re-render writes the new spelling.",
            raw_level,
            LEGACY_LEVEL_ALIASES[raw_level],
            "|".join(OPERATIONAL_LEVELS),
        )
    # A PRESENT block is the user's stated intent, so a field it OMITS must fall back to the
    # conservative value, not to the promoted class default. ADR-013 originally declined this
    # predicate as over-reach; two independent second-opinion models and a docs trace
    # overturned that on new evidence: because every previously-rendered harness.yaml spells
    # out all six autonomy fields and is round-tripped verbatim, a partial block is the ONLY
    # way the flip can reach an existing project — and it reaches it in the worst shape.
    # `autonomy: {autopilot_persistent: false}` inheriting `level: auto_safe` overrides an
    # explicit refusal; `autonomy: {step_cap: 20}` auto-arms someone who only set a limit.
    # The two omitted fields are exactly the two ADR-010 flipped; every other field keeps its
    # ordinary class default, so this is scoped to the flip, not a general strictness change.
    # Build a copy: the branches above copy only conditionally, so `value` may still be the
    # caller's own dict from the parsed yaml, and mutating it in place would be a side effect
    # on data the caller still holds.
    value = {"level": "gated", "autopilot_persistent": False, **value}
    try:
        return AutonomyConfig.model_validate(value, strict=False)
    except Exception as e:  # noqa: BLE001 — tolerant upgrade path like second_brain
        logger.warning("harness.yaml autonomy: invalid config ignored (%s).", e)
        # ADR-013: pinned gated — one bad enum must never be the thing that arms autopilot.
        # But demote the LEVEL, not the whole block: an unknown level used to take the user's
        # caps, pipeline and extra_deny down with it, so a single typo silently reset a
        # security-relevant additive deny baseline. Retry with the level forced conservative
        # and every sibling intact; only a block that is broken beyond the level falls all the
        # way through.
        try:
            return AutonomyConfig.model_validate(
                {**value, "level": "gated", "autopilot_persistent": False}, strict=False
            )
        except Exception:  # noqa: BLE001 — same tolerant contract
            return AutonomyConfig(level="gated", autopilot_persistent=False)


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
                "comprehension": interview_comprehension_defaults(),
            },
            "max_review_rounds": review_rounds,
            "schema_version": schema_version,
        }
    return {
        "models": {"default": "opus", "lite": "sonnet"},
        "autoloop": {"allowed": True, "default_max_iter": 5},
        "memory": {"per_repo": True},
        "anti_rot": {"enabled": True, "sources": 4},
        # PLAN-worktree-side-defaults ADR-001/002/007: one live key. Production
        # defaults to isolation ON (all seven stages in the per-task worktree);
        # Side defaults OFF above. Both are overridable — see `_ask_worktree`,
        # `--worktree/--no-worktree`, and the /hm:configure dimension.
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
            "comprehension": interview_comprehension_defaults(),
        },
        "schema_version": schema_version,
    }
