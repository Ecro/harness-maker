"""Tests for the Interviewer (autoloop + interactive modes)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from harness_maker.interview import interview
from harness_maker.models import (
    AtomicStage,
    DevMode,
    InterviewAnswers,
    Preset,
    ProjectProfile,
)


def _profile(scale: str = "small", lifecycle: str = "experiment") -> ProjectProfile:
    return ProjectProfile(
        stack=["python"],
        scale=scale,
        lifecycle=lifecycle,
        existing_dotclaude=False,
        spec_only=False,
        vault_member=False,
    )


def test_interview_autoloop_returns_typed_answers() -> None:
    result = interview(_profile(), autoloop_mode=True)
    assert isinstance(result, InterviewAnswers)
    assert result.locale == "en"
    assert result.preset == Preset.SIDE
    # Side starter set: exec-rev, exec-rev-wrap, plan-exec-rev-wrap
    assert "exec-rev" in result.fused_workflows
    assert "exec-rev-wrap" in result.fused_workflows
    assert result.default_workflow == "exec-rev-wrap"
    assert result.consensus
    assert result.caching
    assert result.models
    assert result.autoloop is not None
    assert result.memory is not None
    assert result.anti_rot is not None
    assert result.worktree is not None
    assert result.security is not None
    assert result.context_lint is not None
    assert "installed" in result.reviewers
    assert "enabled" in result.reviewers


def test_interview_autoloop_recommends_task_driven_for_side() -> None:
    """Side preset gets task-driven by default — lighter, no SPEC enforcement."""
    result = interview(_profile(), autoloop_mode=True)
    assert result.dev_mode == DevMode.TASK_DRIVEN


def test_interview_autoloop_recommends_spec_driven_for_production() -> None:
    result = interview(_profile(scale="medium", lifecycle="active"), autoloop_mode=True)
    assert result.dev_mode == DevMode.SPEC_DRIVEN


def test_interview_recommends_side_for_experiment_small() -> None:
    result = interview(_profile(scale="small", lifecycle="experiment"), autoloop_mode=True)
    assert result.preset == Preset.SIDE
    assert result.consensus == "single"
    assert result.caching == "agent-aware"
    assert result.reviewers["enabled"] == ["code-reviewer"]
    assert result.autoloop == {"allowed": False}


def test_interview_recommends_production_for_active_medium() -> None:
    result = interview(_profile(scale="medium", lifecycle="active"), autoloop_mode=True)
    assert result.preset == Preset.PRODUCTION
    assert result.consensus == "cross-check"
    assert "code-reviewer" in result.reviewers["enabled"]
    assert "security-reviewer" in result.reviewers["enabled"]
    assert result.autoloop["allowed"] is True
    assert result.context_lint["enabled"] is True


def test_interview_recommends_production_for_large_scale() -> None:
    result = interview(_profile(scale="large", lifecycle="active"), autoloop_mode=True)
    assert result.preset == Preset.PRODUCTION
    assert result.consensus == "cross-check"


def test_interview_installs_all_reviewers_and_skills() -> None:
    """Both presets install full inventory; only `enabled` differs."""
    side = interview(_profile(), autoloop_mode=True)
    prod = interview(_profile(scale="medium", lifecycle="active"), autoloop_mode=True)
    # Same installed inventory regardless of preset
    assert side.reviewers["installed"] == prod.reviewers["installed"]
    assert side.skills["installed"] == prod.skills["installed"]
    # Side enables fewer than Production
    assert len(side.reviewers["enabled"]) < len(prod.reviewers["enabled"])
    assert len(side.skills["enabled"]) <= len(prod.skills["enabled"])


def test_interview_interactive_accepts_recommended(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty answers ⇒ accept recommended locale/preset/dev_mode/starter/defaults."""
    # locale, preset, dev_mode, use-recommended?, default workflow, consensus, caching
    inputs: Iterator[str] = iter(["", "", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.locale == "en"
    assert result.preset == Preset.SIDE
    assert result.dev_mode == DevMode.TASK_DRIVEN  # Side default
    assert result.default_workflow == "exec-rev-wrap"


def test_interview_locale_first_question_accepts_arbitrary_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Locale is the first prompt; user types ``ja`` and it passes through."""
    inputs: Iterator[str] = iter(["ja", "", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.locale == "ja"


def test_interview_dev_mode_explicit_override_to_spec_driven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Side+spec-driven cross is allowed (independent of preset)."""
    # locale, preset, dev_mode=spec, use-rec?, default, consensus, caching
    inputs: Iterator[str] = iter(["", "", "spec", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.preset == Preset.SIDE
    assert result.dev_mode == DevMode.SPEC_DRIVEN


def test_interview_dev_mode_explicit_override_to_task_on_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production+task-driven cross is allowed."""
    inputs: Iterator[str] = iter(["", "Production", "task", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.preset == Preset.PRODUCTION
    assert result.dev_mode == DevMode.TASK_DRIVEN


def test_interview_interactive_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """User picks a different default workflow from the starter set."""
    inputs: Iterator[str] = iter(["", "", "", "", "exec-rev", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.default_workflow == "exec-rev"


def test_interview_interactive_custom_workflows(monkeypatch: pytest.MonkeyPatch) -> None:
    """User declines recommended set and defines a custom workflow."""
    # locale, preset, dev_mode, use-rec?, stages-#1, name-#1, stages-#2 (done),
    # default, consensus, caching
    inputs: Iterator[str] = iter(
        ["", "", "", "n", "4,5", "", "done", "", "", ""],
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.fused_workflows == {
        "exec-rev": [AtomicStage.EXECUTE, AtomicStage.REVIEW],
    }
    assert result.default_workflow == "exec-rev"


def test_interview_interactive_custom_named_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User overrides the auto-generated workflow name."""
    inputs: Iterator[str] = iter(
        ["", "", "", "n", "4,5,6", "ship", "done", "", "", ""],
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert "ship" in result.fused_workflows
    assert result.fused_workflows["ship"] == [
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ]


def test_interview_preset_override_to_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """User on a small-experiment profile picks Production explicitly."""
    inputs: Iterator[str] = iter(["", "Production", "", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.preset == Preset.PRODUCTION
    assert result.default_workflow == "exec-rev-wrap-ver"


def test_interview_custom_workflow_rejects_reserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cannot name a custom workflow with a reserved word; user re-prompted."""
    # locale, preset, dev_mode, use-rec?, stages-#1, name=plan (reserved → re-prompt),
    # stages-#1 again (3,4), name (auto), done, default, consensus, caching
    inputs: Iterator[str] = iter(
        ["", "", "", "n", "4,5", "plan", "3,4", "", "done", "", "", ""],
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    # The reserved-name attempt was rejected; only the second valid entry remains.
    assert "plan" not in result.fused_workflows
    assert "plan-exec" in result.fused_workflows
