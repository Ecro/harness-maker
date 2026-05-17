"""Phase 10 — B2 Pass 1 + Pass 1.5 skip when reviewer count == 1."""

from __future__ import annotations

from pathlib import Path

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render_preset(tmp_path: Path, preset: Preset) -> Path:
    profile = (
        ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
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


def test_review_skips_verifier_when_single_reviewer(tmp_path: Path) -> None:
    """Side preset (1 reviewer) should skip Pass 1.5 verifier block (C2 validator)."""
    out = _render_preset(tmp_path, Preset.SIDE)
    review = (out / "stages" / "review.md").read_text(encoding="utf-8")
    assert "Pass 1.5 — verifier" not in review
    assert "code-verifier" not in review


def test_review_includes_verifier_when_multi_and_a8_active(tmp_path: Path) -> None:
    """Production (multi-reviewer) should include Pass 1.5 verifier (A8 active)."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    review = (out / "stages" / "review.md").read_text(encoding="utf-8")
    assert "Pass 1.5" in review
    assert "code-verifier" in review
