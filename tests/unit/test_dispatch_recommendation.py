"""Tri-IDE payload-equivalence tests for _dispatch_recommendation (validator N1).

Phase 8 makes _dispatch_recommendation the single Python-side site that fans
the same Recommendation out to Claude Code / Cursor / Codex via the rendered
slash command. The Python-side contract MUST be target-agnostic: for the
same Recommendation, the function returns the same value regardless of the
``target`` argument. Tests here pin that invariant so future refactors can't
silently drift one IDE's payload away from the others.
"""

from __future__ import annotations

import pytest

from harness_maker.interview import _dispatch_recommendation
from harness_maker.models import (
    Confidence,
    Preset,
    Recommendation,
    RecommendationEvidence,
    Target,
)


def _rec(value: object, confidence: Confidence, axis: str = "preset") -> Recommendation:
    """Build a Recommendation with mirrored evidence — ADR-011 invariant."""
    return Recommendation(
        axis=axis,
        value=value,
        confidence=confidence,
        evidence=RecommendationEvidence(
            n_observations=1,
            top_3_signals=["test"],
            confidence=confidence,
        ),
        signal="test signal",
    )


@pytest.mark.parametrize("target", [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX])
def test_dispatch_tri_ide_high_returns_same_value(target: Target) -> None:
    """HIGH rec: all three targets get the recommendation value silently."""
    rec = _rec(Preset.SIDE, Confidence.HIGH)
    out = _dispatch_recommendation(rec, target=target, input_provider=lambda _p: "")
    assert out == Preset.SIDE


@pytest.mark.parametrize("target", [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX])
def test_dispatch_tri_ide_low_returns_none(target: Target) -> None:
    """LOW rec: all three targets get None (no surface)."""
    rec = _rec(Preset.SIDE, Confidence.LOW)
    out = _dispatch_recommendation(rec, target=target, input_provider=lambda _p: "")
    assert out is None


@pytest.mark.parametrize("target", [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX])
def test_dispatch_tri_ide_medium_accept_returns_same_value(target: Target) -> None:
    """MEDIUM rec + accept (Y/blank): all three targets return rec.value."""
    rec = _rec(Preset.SIDE, Confidence.MEDIUM)
    out = _dispatch_recommendation(rec, target=target, input_provider=lambda _p: "y")
    assert out == Preset.SIDE


@pytest.mark.parametrize("target", [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX])
def test_dispatch_tri_ide_medium_reject_returns_none(target: Target) -> None:
    """MEDIUM rec + reject ('n'): all three targets return None."""
    rec = _rec(Preset.SIDE, Confidence.MEDIUM)
    out = _dispatch_recommendation(rec, target=target, input_provider=lambda _p: "n")
    assert out is None


def test_dispatch_tri_ide_payload_equivalence() -> None:
    """For the SAME Recommendation, all three targets produce the same return.

    Validator N1: tri-IDE drift guard. The Python contract is target-agnostic;
    only the (future) slash-command rendering layer differs per IDE.
    """
    rec_high = _rec(Preset.PRODUCTION, Confidence.HIGH)
    rec_medium = _rec(Preset.PRODUCTION, Confidence.MEDIUM)
    rec_low = _rec(Preset.PRODUCTION, Confidence.LOW)

    outs_high = [
        _dispatch_recommendation(rec_high, target=t, input_provider=lambda _p: "")
        for t in (Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX)
    ]
    outs_medium_accept = [
        _dispatch_recommendation(rec_medium, target=t, input_provider=lambda _p: "yes")
        for t in (Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX)
    ]
    outs_medium_reject = [
        _dispatch_recommendation(rec_medium, target=t, input_provider=lambda _p: "n")
        for t in (Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX)
    ]
    outs_low = [
        _dispatch_recommendation(rec_low, target=t, input_provider=lambda _p: "")
        for t in (Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX)
    ]

    # All three must agree per bucket.
    assert outs_high == [Preset.PRODUCTION, Preset.PRODUCTION, Preset.PRODUCTION]
    assert outs_medium_accept == [Preset.PRODUCTION, Preset.PRODUCTION, Preset.PRODUCTION]
    assert outs_medium_reject == [None, None, None]
    assert outs_low == [None, None, None]
