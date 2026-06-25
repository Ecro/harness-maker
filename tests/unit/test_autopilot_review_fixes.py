"""PLAN-autopilot-config-surface — regression tests for the two Codex (k-of-3) review findings.

P1: with caps now nullable (unlimited), a duplicate-stage pipeline (`[execute, execute]`) would
loop forever because `next_stage()` resolves by first index — the boundedness invariant assumed
uniqueness. Both `AutonomyConfig.pipeline` and `AutopilotMarker.pipeline` now reject duplicates,
so no marker the boundary CLI consumes can be non-monotonic, and the autoarm hook fail-safe-skips.

P2: `_parse_autonomy(strict=False)` (needed for stage-string→enum coercion) would also coerce a
hand-edited non-bool `autopilot_persistent` ("true"/1) into a real bool and re-render it committed,
defeating the autoarm hook's strict `is True` guard. Non-bool values now fall to the safe default.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker import autopilot
from harness_maker.autopilot import AutopilotMarker
from harness_maker.hooks import autopilot_autoarm
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.io_utils import atomic_write
from harness_maker.models import AtomicStage, AutonomyConfig

_DUP = [AtomicStage.EXECUTE, AtomicStage.EXECUTE]


# ── P1: duplicate-stage pipelines are rejected at both validation chokepoints ──


def test_autonomy_config_rejects_duplicate_pipeline() -> None:
    with pytest.raises(ValidationError):
        AutonomyConfig(pipeline=_DUP)


def test_marker_rejects_duplicate_pipeline() -> None:
    with pytest.raises(ValidationError):
        AutopilotMarker(
            session_uuid="0123456789ab",
            level="auto_safe",
            pipeline=_DUP,
            created_at="2026-06-25T12:00:00+00:00",
        )


def test_autoarm_fail_safe_on_duplicate_pipeline(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    atomic_write(
        tmp_path / ".claude" / "harness.yaml",
        "preset: Production\nautonomy:\n  level: auto_safe\n"
        "  pipeline: [execute, execute]\n  autopilot_persistent: true\n",
    )
    # AutopilotMarker rejects the duplicate → autopilot.write raises → hook fail-safe-skips.
    assert autopilot_autoarm.arm_if_persistent(tmp_path, now="2026-06-25T12:00:00+00:00") is False
    assert autopilot.load(tmp_path) is None


# ── P2: non-bool autopilot_persistent is NOT coerced to True on re-render ──────


def _write(root: Path, persistent_literal: str) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    p = root / ".claude" / "harness.yaml"
    atomic_write(
        p,
        "preset: Production\nlocale: en\ntargets: [claude-code]\n"
        f"autonomy:\n  level: auto_safe\n  autopilot_persistent: {persistent_literal}\n",
    )
    return p


@pytest.mark.parametrize("literal", ['"true"', "1", '"yes"', '"1"'])
def test_parse_autonomy_non_bool_persistent_falls_to_false(tmp_path: Path, literal: str) -> None:
    answers = answers_from_harness_yaml(_write(tmp_path, literal))
    assert answers is not None
    assert answers.autonomy.autopilot_persistent is False


def test_parse_autonomy_real_bool_persistent_preserved(tmp_path: Path) -> None:
    # A genuine yaml boolean is still honored — only non-bools are stripped.
    answers = answers_from_harness_yaml(_write(tmp_path, "true"))
    assert answers is not None
    assert answers.autonomy.autopilot_persistent is True
