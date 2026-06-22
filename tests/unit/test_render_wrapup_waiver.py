"""Phase 3 — wrapup Step 3.6 oracle-waiver advisory renders only on task-driven.

PLAN-wrapup-waiver-enforcement ADR-003/004: the advisory is dev_mode-branched
at render time. task-driven renders the `waiver-check` call; spec-driven omits
it entirely (spec-driven already blocks at /hm:spec authoring).
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import DevMode, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _wrapup(tmp_path: Path, dev_mode: DevMode) -> str:
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE], dev_mode=dev_mode),
    )
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return next(f.read_text(encoding="utf-8") for f in tmp_path.rglob("stages/wrapup.md"))


def test_task_driven_renders_waiver_advisory(tmp_path: Path) -> None:
    body = _wrapup(tmp_path, DevMode.TASK_DRIVEN)
    assert "waiver-check" in body
    assert "Step 3.6" in body
    # Advisory, never a STOP.
    assert "NEVER a STOP" in body


def test_spec_driven_omits_waiver_advisory(tmp_path: Path) -> None:
    body = _wrapup(tmp_path, DevMode.SPEC_DRIVEN)
    assert "waiver-check" not in body
    assert "Step 3.6" not in body
