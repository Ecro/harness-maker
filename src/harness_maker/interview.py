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

from typing import Any

from harness_maker.models import (
    AtomicStage,
    DevMode,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    auto_workflow_name,
)
from harness_maker.validators import validate_workflow_name

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
]

_SIDE_ENABLED_REVIEWERS: list[str] = ["code-reviewer"]
_SIDE_ENABLED_SKILLS: list[str] = [
    "verify-before-completion",
    "autoloop-driver",
    "ai-readiness-rubric",
    "agent-quality-rubric",
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
            preset=recommended,
            dev_mode=_recommend_dev_mode(recommended),
            fused_workflows=_starter_for(recommended),
            default_workflow=_default_for(recommended),
        )

    print(
        f"\nDetected: stack={profile.stack}, scale={profile.scale}, "
        f"lifecycle={profile.lifecycle}",
    )
    locale = _ask_locale()
    preset = _ask_preset(recommended)
    dev_mode = _ask_dev_mode(preset)
    fused, default_name = _ask_fused_workflows(preset)
    consensus = _ask_with_default("consensus", _consensus_for(preset))
    caching = _ask_with_default("caching", "agent-aware")
    return _build_answers(
        locale=locale,
        preset=preset,
        dev_mode=dev_mode,
        fused_workflows=fused,
        default_workflow=default_name,
        consensus=consensus,
        caching=caching,
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
# Dev mode (independent axis; recommended per preset, any cross allowed)
# ──────────────────────────────────────────────────────────────────────────────


def _recommend_dev_mode(preset: Preset) -> DevMode:
    """Side defaults to task-driven (lighter), Production defaults to spec-driven."""
    return DevMode.TASK_DRIVEN if preset == Preset.SIDE else DevMode.SPEC_DRIVEN


def _ask_dev_mode(preset: Preset) -> DevMode:
    recommended = _recommend_dev_mode(preset)
    other = (
        DevMode.SPEC_DRIVEN
        if recommended == DevMode.TASK_DRIVEN
        else DevMode.TASK_DRIVEN
    )
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
    chosen = (
        starter
        if use_default in ("", "y", "yes")
        else (_ask_custom_workflows() or starter)
    )

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
    preset: Preset,
    dev_mode: DevMode,
    fused_workflows: dict[str, list[AtomicStage]],
    default_workflow: str,
    consensus: str | None = None,
    caching: str | None = None,
) -> InterviewAnswers:
    is_side = preset == Preset.SIDE
    return InterviewAnswers(
        locale=locale,
        preset=preset,
        dev_mode=dev_mode,
        fused_workflows=fused_workflows,
        default_workflow=default_workflow,
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
