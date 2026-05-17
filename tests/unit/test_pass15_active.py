"""Phase 9 — A8 Pass 1.5 code-verifier activation tests."""

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


def test_review_pass_15_active(tmp_path: Path) -> None:
    """Review template must contain an active Pass 1.5 verifier invocation."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    review = (out / "stages" / "review.md").read_text(encoding="utf-8")
    assert "Pass 1.5" in review
    assert "code-verifier" in review
    assert "deferred" not in review.lower().split("pass 1.5")[1].split("pass 2")[0]
    assert "KEEP" in review or "kept" in review
    assert "DROP" in review or "dropped" in review


def test_review_pass_15_feeds_pass_2(tmp_path: Path) -> None:
    """Pass 2 should reference verified findings, not raw Pass 1."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    review = (out / "stages" / "review.md").read_text(encoding="utf-8")
    pass2_section = review[review.find("Pass 2"):]
    assert "verified findings" in pass2_section or "Pass 1.5" in pass2_section


def test_code_verifier_agent_exists(tmp_path: Path) -> None:
    """The code-verifier agent must be rendered."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    agent = out / "agents" / "code-verifier.md"
    assert agent.is_file()
    content = agent.read_text(encoding="utf-8")
    assert "reduce-only" in content.lower() or "KEEP" in content
