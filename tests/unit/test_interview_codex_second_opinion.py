"""Phase 3 — interactive interview question for codex_second_opinion.

PLAN-codex-second-llm-integration Phase 3: 1 yes/no question added after
the existing flow; default (empty input) is no.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


def test_interview_empty_input_defaults_codex_second_opinion_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pressing Enter at every prompt yields enabled=False (safe default)."""
    # 13 empty answers: 11 pre-existing + codex + the new autopilot-enable question
    inputs: Iterator[str] = iter([""] * 13)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.codex_second_opinion.enabled is False


def test_interview_y_answer_enables_codex_second_opinion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User typing 'y' as the codex-second-opinion answer flips enabled to True."""
    # 11 empty + 'y' for the codex question, then '' for the new autopilot-enable question
    inputs: Iterator[str] = iter([""] * 11 + ["y", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.codex_second_opinion.enabled is True
    # Allow-list defaults preserved (no follow-up question for agents).
    assert result.codex_second_opinion.agents == [
        "code-reviewer",
        "consensus-arbiter",
        "plan-validator",
    ]


def test_interview_autoloop_defaults_codex_second_opinion_disabled() -> None:
    """autoloop_mode skips all prompts; codex_second_opinion stays disabled."""
    result = interview(_profile(), autoloop_mode=True)
    assert result.codex_second_opinion.enabled is False
