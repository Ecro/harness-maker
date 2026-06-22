"""Render assertions for non-mechanical AC forward-binding (PLAN-nonmechanical-ac-binding).

- execute Phase A (d) authors parametric tests from the golden_table SSOT.
- wrapup Step 3.5 write-back + per-type report cover property/parametric and flip the
  old "EXPECTED to remain pending" wording; the Production block is preset-branched.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _stage(tmp_path: Path, preset: Preset, stage: str) -> str:
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=preset, targets=[Target.CLAUDE_CODE]),
    )
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return next(f.read_text(encoding="utf-8") for f in tmp_path.rglob(f"stages/{stage}.md"))


def test_execute_renders_parametric_authoring(tmp_path: Path) -> None:
    body = _stage(tmp_path, Preset.PRODUCTION, "execute")
    assert "Parametric ACs" in body
    assert "load_golden_table" in body
    assert "golden_table` is the SSOT" in body
    # data-loading only — the author writes the oracle body (not a universal recipe).
    assert "data-loading ONLY" in body


def test_wrapup_writeback_covers_property_and_parametric(tmp_path: Path) -> None:
    body = _stage(tmp_path, Preset.PRODUCTION, "wrapup")
    assert "select_pytest_bindable" in body
    assert "judgment, deferred" in body
    # the old half-state wording must be gone.
    assert "EXPECTED to remain\n  pending until the parametric/judgment" not in body
    assert "EXPECTED to remain pending" not in body


def test_wrapup_production_renders_fail_closed_block(tmp_path: Path) -> None:
    body = _stage(tmp_path, Preset.PRODUCTION, "wrapup")
    assert "find-unbound" in body
    assert "fail-closed" in body
    assert "Production enforcement" in body


def test_wrapup_side_renders_advisory_not_block(tmp_path: Path) -> None:
    body = _stage(tmp_path, Preset.SIDE, "wrapup")
    # Side still names find-unbound (to list), but as advisory — no Production STOP block.
    assert "advisory only" in body
    assert "Production enforcement" not in body
