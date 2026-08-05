"""Phase 10 — B2 Pass 1 + Pass 1.5 skip when reviewer count == 1."""

from __future__ import annotations

from pathlib import Path

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render_preset(tmp_path: Path, preset: Preset) -> Path:
    profile = (
        ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
        if preset == Preset.SIDE
        else ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    )
    a = interview(profile, autoloop_mode=True)
    bp = synthesize(profile, a, preset=preset)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def test_review_skips_pass1_when_single_reviewer(tmp_path: Path) -> None:
    """Side preset (1 reviewer) should skip Pass 1 redaction."""
    out = _render_preset(tmp_path, Preset.SIDE)
    review = (out / "stages" / "review.md").read_text(encoding="utf-8")
    assert "single reviewer" in review.lower()
    assert "Pass 1 — rubric-only" not in review


def test_review_includes_pass1_when_multi(tmp_path: Path) -> None:
    """Production preset (multi-reviewer) should include Pass 1."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    review = (out / "stages" / "review.md").read_text(encoding="utf-8")
    assert "Pass 1 — rubric-only" in review


def test_no_verifier_block_under_either_preset(tmp_path: Path) -> None:
    """ADR-001 removed the Pass 1.5 dispatch on BOTH arms — it is no longer preset-dependent.

    This replaces a pair of tests that asserted "Side skips the verifier / Production
    includes it". After the removal the Production one still passed, because
    `assert "Pass 1.5" in review` matched the *removal notice* — documentation about the
    deletion satisfying a test that the thing exists. The Side one still passed too, for the
    unrelated reason that the single-reviewer branch never rendered the notice.

    Anchored on the heading, not the words: `"Pass 1.5 — verifier"` is the block's own
    `####` title and appears nowhere in the prose that explains its removal.
    """
    for preset in (Preset.SIDE, Preset.PRODUCTION):
        out = _render_preset(tmp_path / preset.value, preset)
        review = (out / "stages" / "review.md").read_text(encoding="utf-8")
        assert "#### Pass 1.5 — verifier" not in review, f"{preset.value}: the block is back"
