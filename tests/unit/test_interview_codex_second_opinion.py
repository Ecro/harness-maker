"""Phase 3 — interactive interview question for second_opinion (multi-model).

PLAN-second-opinion-multi-model: `_ask_codex_second_opinion` (a single yes/no
question) was replaced by `_ask_second_opinion`, a comma-separated multi-select
over `codex`/`antigravity` (default empty input = disabled). Selecting
`antigravity` triggers one extra prompt (`_ask_antigravity_model`), which shells
out to `agy models` at interview time (ADR-007) and falls back to a hardcoded
default when the CLI is unavailable/unauthenticated — `_fetch_agy_models` is
monkeypatched in every test that selects antigravity so results don't depend on
whether the host machine has `agy` installed.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


def test_interview_empty_input_defaults_second_opinion_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pressing Enter at every prompt yields models=[] (safe default)."""
    # 13 empty answers: 11 pre-existing + second_opinion + the autopilot-enable question.
    inputs: Iterator[str] = iter([""] * 13)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.second_opinion.enabled is False
    assert result.second_opinion.models == []


def test_interview_codex_answer_enables_second_opinion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User typing 'codex' as the second-opinion answer selects only codex."""
    # 11 empty + 'codex' for the second-opinion question, then '' for autopilot.
    inputs: Iterator[str] = iter([""] * 11 + ["codex", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.second_opinion.enabled is True
    assert result.second_opinion.models == ["codex"]
    # Allow-list defaults preserved (no follow-up question for agents).
    assert result.second_opinion.agents == [
        "code-reviewer",
        "consensus-arbiter",
        "plan-validator",
    ]


def test_interview_multi_model_answer_enables_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User typing 'codex,antigravity' selects both models (ADR-002: independent,
    both-at-once allowed). No `agy` on the test host -> the antigravity model
    prompt falls back to the hardcoded default without consuming extra input."""
    monkeypatch.setattr("harness_maker.interview._fetch_agy_models", lambda: [])
    # 11 empty + 'codex,antigravity' for the second-opinion question, then '' for autopilot.
    inputs: Iterator[str] = iter([""] * 11 + ["codex,antigravity", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.second_opinion.enabled is True
    assert result.second_opinion.models == ["codex", "antigravity"]
    assert result.second_opinion.antigravity.model == "Gemini 3.1 Pro (High)"


def test_interview_antigravity_answer_prompts_for_model_pick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting antigravity with a live `agy models` list prompts for a pick;
    the chosen list entry is persisted as the antigravity model pin."""
    monkeypatch.setattr(
        "harness_maker.interview._fetch_agy_models",
        lambda: ["Model A", "Model B"],
    )
    # 11 empty + 'antigravity' (enable) + '2' (pick Model B) + '' (autopilot).
    inputs: Iterator[str] = iter([""] * 11 + ["antigravity", "2", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.second_opinion.enabled is True
    assert result.second_opinion.models == ["antigravity"]
    assert result.second_opinion.antigravity.model == "Model B"


def test_interview_unknown_model_token_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognized token in the comma-separated answer is dropped with a
    warning, not raised — only the recognized 'codex' survives."""
    inputs: Iterator[str] = iter([""] * 11 + ["codex,bogus", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    result = interview(_profile(), autoloop_mode=False)
    assert result.second_opinion.models == ["codex"]


def test_interview_autoloop_defaults_second_opinion_disabled() -> None:
    """autoloop_mode skips all prompts; second_opinion stays disabled."""
    result = interview(_profile(), autoloop_mode=True)
    assert result.second_opinion.enabled is False
    assert result.second_opinion.models == []
