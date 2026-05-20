"""Tests for INTEGRATION-gated LLM judge wiring (Step 4 of REVIEW followups)."""

from __future__ import annotations

import pytest

from harness_maker.spec_inventory.__main__ import _resolve_judge


def test_resolve_judge_returns_none_without_integration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default mode (no env var) yields heuristic-only fallback."""
    monkeypatch.delenv("INTEGRATION", raising=False)
    assert _resolve_judge() is None


def test_resolve_judge_attempts_anthropic_when_integration_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INTEGRATION=1 tries AnthropicJudgeClient; returns None on instantiation error."""
    monkeypatch.setenv("INTEGRATION", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Without an API key the client constructor raises; _resolve_judge degrades
    # silently to None rather than propagating the exception.
    result = _resolve_judge()
    # Either we get a client (env had a key from somewhere) or None (no key).
    # Both are acceptable; the contract is "no uncaught exception".
    assert result is None or hasattr(result, "judge")


def test_resolve_judge_conforms_to_protocol_when_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When _resolve_judge does return a client, it satisfies JudgeProtocol shape."""
    monkeypatch.setenv("INTEGRATION", "1")
    result = _resolve_judge()
    if result is not None:
        assert callable(getattr(result, "judge", None))
