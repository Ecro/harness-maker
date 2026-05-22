"""Tests for A2 drift gate cascade demote (Phase 6)."""

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


def test_review_emits_drift_verdict(tmp_path: Path) -> None:
    """Review template must instruct emitting drift_verdict in frontmatter."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    review = (out / "stages" / "review.md").read_text(encoding="utf-8")
    assert "drift_verdict" in review
    assert "task_slug" in review
    assert "SINGLE OWNER" in review or "single owner" in review.lower()


def test_wrapup_reads_verdict_not_reanalyzes(tmp_path: Path) -> None:
    """Wrapup must read drift_verdict, not re-run drift analysis."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    wrapup = (out / "stages" / "wrapup.md").read_text(encoding="utf-8")
    assert "drift_verdict" in wrapup
    assert "read-only" in wrapup.lower() or "no LLM re-analysis" in wrapup
    # Step 3 must NOT contain the old advisory analysis pattern
    step3_start = wrapup.find("Step 3")
    step4_start = wrapup.find("Step 4")
    if step3_start >= 0 and step4_start > step3_start:
        step3_text = wrapup[step3_start:step4_start]
        assert "Files staged but NOT" not in step3_text, "Step 3 should not re-analyze drift"


def test_wrapup_blocks_on_missing_review(tmp_path: Path) -> None:
    """Wrapup must instruct FAIL when drift_verdict is absent."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    wrapup = (out / "stages" / "wrapup.md").read_text(encoding="utf-8")
    assert "BLOCKED" in wrapup or "FAIL" in wrapup
    assert "/hm:review" in wrapup


def test_verify_blocks_on_stale_review_slug(tmp_path: Path) -> None:
    """Verify must instruct FAIL when drift_verdict task_slug doesn't match."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    verify = (out / "stages" / "verify.md").read_text(encoding="utf-8")
    assert "drift_verdict" in verify
    assert "task_slug" in verify
    assert "BLOCKED" in verify or "FAIL" in verify


def test_wrapup_passes_on_matching_verdict(tmp_path: Path) -> None:
    """Wrapup must have path for proceeding when verdict is present and matching."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    wrapup = (out / "stages" / "wrapup.md").read_text(encoding="utf-8")
    assert "continue" in wrapup.lower() or "proceed" in wrapup.lower()
