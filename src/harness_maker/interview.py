"""Interview the user (or accept defaults) to derive InterviewAnswers from a profile."""

from __future__ import annotations

from typing import Any

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile
from harness_maker.validators import validate_workflow_names


def interview(
    profile: ProjectProfile,
    autoloop_mode: bool = False,
) -> InterviewAnswers:
    """Return typed answers; autoloop_mode=True takes all defaults silently."""
    preset = _recommend_preset(profile)
    defaults = _defaults_for_preset(preset)
    if autoloop_mode:
        # Preset seeds are exempt from the reserved-word check (amendment §F);
        # validate_workflow_names handles that.
        validate_workflow_names(defaults["workflow_names"])
        return InterviewAnswers(**defaults)
    answers = dict(defaults)
    # Interactive override loop — minimal Phase 2 UX; Phase 6 adds workflow naming.
    for dimension in [
        "default_workflow",
        "consensus",
        "caching",
    ]:
        current = answers[dimension]
        prompt = f"{dimension} [{current}]: "
        try:
            user_input = input(prompt).strip()
        except EOFError:
            user_input = ""
        if user_input:
            answers[dimension] = user_input
    # Phase 6 workflow naming override (interactive only).
    # Empty input keeps the seeded list unchanged. Comma-separated values
    # replace the list; reserved-word check applies (amendment §F).
    seeded = ",".join(answers["workflow_names"])
    try:
        wf_input = input(f"workflow_names [{seeded}]: ").strip()
    except EOFError:
        wf_input = ""
    if wf_input:
        new_names = [n.strip() for n in wf_input.split(",") if n.strip()]
        validate_workflow_names(new_names)
        answers["workflow_names"] = new_names
        if answers["default_workflow"] not in new_names:
            answers["default_workflow"] = new_names[0]
    else:
        validate_workflow_names(answers["workflow_names"])
    return InterviewAnswers(**answers)


def _recommend_preset(profile: ProjectProfile) -> Preset:
    """Heuristic: small project that's experimental or in maintenance → Side; else Production."""
    if profile.scale == "small" and profile.lifecycle in {"experiment", "maintenance"}:
        return Preset.SIDE
    return Preset.PRODUCTION


def _defaults_for_preset(preset: Preset) -> dict[str, Any]:
    """Return a sensible default answers dict for the given preset."""
    if preset == Preset.SIDE:
        return {
            "workflow_names": ["dev"],
            "default_workflow": "dev",
            "reviewers": ["code-reviewer"],
            "consensus": "single",
            "caching": "agent-aware",
            "models": {"default": "sonnet"},
            "autoloop": {"allowed": False},
            "memory": {"per_repo": False},
            "anti_rot": {"enabled": False},
            "worktree": {"enabled": False},
            "security": {"gates": []},
            "context_lint": {"enabled": False},
        }
    return {
        "workflow_names": ["dev", "quick", "careful", "audit"],
        "default_workflow": "dev",
        "reviewers": ["code-reviewer", "security-reviewer", "test-reviewer"],
        "consensus": "cross-check",
        "caching": "session+agent",
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
