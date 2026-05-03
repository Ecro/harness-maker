"""Interview the user (or accept defaults) to derive InterviewAnswers from a profile."""

from __future__ import annotations

from typing import Any

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile


def interview(
    profile: ProjectProfile,
    autoloop_mode: bool = False,
) -> InterviewAnswers:
    """Return typed answers; autoloop_mode=True takes all defaults silently."""
    preset = _recommend_preset(profile)
    defaults = _defaults_for_preset(preset)
    if autoloop_mode:
        return InterviewAnswers(**defaults)
    answers = dict(defaults)
    # Interactive override loop — minimal Phase 2 UX (richer prompts in Phase 6).
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
        "workflow_names": ["dev", "ship"],
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
