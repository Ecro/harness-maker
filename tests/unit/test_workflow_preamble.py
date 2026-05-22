"""Phase 7 — A7 fused-workflow memory preamble tests."""

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


def test_workflow_preamble_present(tmp_path: Path) -> None:
    """Fused workflow output must contain Shared Session Context exactly once."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    wf = (out / "commands" / "hm" / "exec-rev-wrap-ver.md").read_text(encoding="utf-8")
    count = wf.count("## Shared Session Context")
    assert count == 1, f"Expected exactly 1 occurrence, found {count}"
    assert "Hot tier" in wf
    assert "failures.md" in wf
    assert "wiki.md" in wf


def test_workflow_preamble_has_config_summary(tmp_path: Path) -> None:
    """Preamble must include harness config summary with preset and workflow name."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    wf = (out / "commands" / "hm" / "exec-rev-wrap-ver.md").read_text(encoding="utf-8")
    assert "Harness config summary" in wf
    assert "Production" in wf
    assert "exec-rev-wrap-ver" in wf


def test_atomic_no_preamble(tmp_path: Path) -> None:
    """Atomic stage output (research.md) must NOT have the shared preamble."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    research = (out / "commands" / "hm" / "research.md").read_text(encoding="utf-8")
    assert "Shared Session Context" not in research


def test_all_fused_workflows_have_preamble(tmp_path: Path) -> None:
    """Every fused workflow should get the preamble, not just exec-rev-wrap-ver."""
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    for name in ("exec-rev.md", "exec-rev-wrap.md", "exec-rev-wrap-ver.md"):
        wf = (out / "commands" / "hm" / name).read_text(encoding="utf-8")
        assert "## Shared Session Context" in wf, f"{name} missing preamble"


def test_side_preset_preamble(tmp_path: Path) -> None:
    """Side preset fused workflows should also get the preamble with Side values."""
    out = _render_preset(tmp_path, Preset.SIDE)
    wf = (out / "commands" / "hm" / "exec-rev-wrap.md").read_text(encoding="utf-8")
    assert "## Shared Session Context" in wf
    assert "Side" in wf
