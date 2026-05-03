"""Tests for the Interviewer (autoloop + interactive modes)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from harness_maker.interview import interview
from harness_maker.models import InterviewAnswers, ProjectProfile


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
    assert result.default_workflow == "dev"
    # All 12 dimensions populated
    assert result.workflow_names
    assert result.consensus
    assert result.caching
    assert result.models is not None
    assert result.autoloop is not None
    assert result.memory is not None
    assert result.anti_rot is not None
    assert result.worktree is not None
    assert result.security is not None
    assert result.context_lint is not None
    assert result.reviewers is not None


def test_interview_recommends_side_for_experiment_small() -> None:
    result = interview(_profile(scale="small", lifecycle="experiment"), autoloop_mode=True)
    assert result.consensus == "single"
    assert result.caching == "agent-aware"
    assert result.reviewers == ["code-reviewer"]
    assert result.autoloop == {"allowed": False}


def test_interview_recommends_production_for_active_medium() -> None:
    result = interview(_profile(scale="medium", lifecycle="active"), autoloop_mode=True)
    assert result.consensus == "cross-check"
    assert "code-reviewer" in result.reviewers
    assert "security-reviewer" in result.reviewers
    assert result.autoloop["allowed"] is True
    assert result.context_lint["enabled"] is True


def test_interview_recommends_production_for_large_scale() -> None:
    result = interview(_profile(scale="large", lifecycle="active"), autoloop_mode=True)
    assert result.consensus == "cross-check"


def test_interview_interactive_mocked_input(monkeypatch: pytest.MonkeyPatch) -> None:
    # Empty input ⇒ accept defaults across the 3 prompted dimensions.
    inputs: Iterator[str] = iter(["", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert isinstance(result, InterviewAnswers)
    assert result.default_workflow == "dev"
    assert result.consensus == "single"


def test_interview_interactive_override(monkeypatch: pytest.MonkeyPatch) -> None:
    # Production profile has workflow_names=['dev', 'ship']; override default_workflow to 'ship'.
    inputs: Iterator[str] = iter(["ship", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(scale="medium", lifecycle="active"), autoloop_mode=False)
    assert result.default_workflow == "ship"
    assert result.consensus == "cross-check"
