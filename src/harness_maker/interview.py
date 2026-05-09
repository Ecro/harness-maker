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

import logging
from pathlib import Path
from typing import Any

import yaml

from harness_maker.models import (
    AtomicStage,
    DevMode,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    RefFolder,
    Target,
    auto_workflow_name,
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
    "plan-exec-rev-wrap": [
        AtomicStage.PLAN,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ],
}
_SIDE_DEFAULT = "exec-rev-wrap"

_PRODUCTION_STARTER: dict[str, list[AtomicStage]] = {
    "exec-rev": [AtomicStage.EXECUTE, AtomicStage.REVIEW],
    "exec-rev-wrap": [
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ],
    "exec-rev-wrap-ver": [
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
        AtomicStage.VERIFY,
    ],
    "res-spec-plan": [
        AtomicStage.RESEARCH,
        AtomicStage.SPEC,
        AtomicStage.PLAN,
    ],
}
_PRODUCTION_DEFAULT = "exec-rev-wrap-ver"

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
    "relevance-filter",
    "worktree-isolator",
    "security-scanner",
    "context-linter",
    "research-crawler",
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
    """Side defaults to task-driven (lighter), Production defaults to spec-driven."""
    return DevMode.TASK_DRIVEN if preset == Preset.SIDE else DevMode.SPEC_DRIVEN


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
    """Heuristic: small + experimental/maintenance → Side; else Production."""
    if profile.scale == "small" and profile.lifecycle in {"experiment", "maintenance"}:
        return Preset.SIDE
    return Preset.PRODUCTION


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
        path_part = path_part.strip()
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
    ref_folders: list[RefFolder] | None = None,
    sibling_repos: list[str] | None = None,
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
        **_preset_extras(preset),
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
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5 :]
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
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

    base = _build_answers(
        locale=_string_or(data.get("locale"), "en"),
        targets=targets,
        preset=preset,
        dev_mode=dev_mode,
        fused_workflows=fused_workflows,
        default_workflow=default_workflow,
        consensus=_string_or(_dig(data, "reviewers", "consensus"), None),
        caching=_string_or(data.get("caching"), None),
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
    sibling_repos = _list_of_strings(data.get("sibling_repos"))

    update: dict[str, Any] = {
        "domains": domains,
        "ref_folders": ref_folders,
        "sibling_repos": sibling_repos,
        "reviewers": {
            "installed": list(base.reviewers["installed"]),
            "enabled": reviewers_enabled,
        },
        "skills": {
            "installed": list(base.skills["installed"]),
            "enabled": skills_enabled,
        },
    }
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
        # Always write through so an explicit `mechanical_checks: []` clears the field.
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


def _preset_extras(preset: Preset) -> dict[str, Any]:
    if preset == Preset.SIDE:
        return {
            "models": {"default": "sonnet"},
            "autoloop": {"allowed": False},
            "memory": {"per_repo": False},
            "anti_rot": {"enabled": False},
            "worktree": {"enabled": False},
            "security": {"gates": []},
            "context_lint": {"enabled": False},
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
    }
