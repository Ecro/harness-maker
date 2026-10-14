"""SPEC-hm-autopilot-spec-advance AC-003 — the auto_full spec directive says to advance.

The directive told the agent to write no approval and never said the missing approval is no
reason to stop; 6 of 15 bench runs stopped on exactly that reading with `proceed: true` in hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker import autopilot, autopilot_caps
from harness_maker.models import AtomicStage


def test_directive_says_a_missing_approval_is_no_reason_to_stop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pipeline = [
        AtomicStage.RESEARCH,
        AtomicStage.SPEC,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.VERIFY,
        AtomicStage.WRAPUP,
    ]
    autopilot.write(tmp_path, level="auto_full", pipeline=pipeline)
    argv = ["boundary", "--root", str(tmp_path), "--current", "spec", "--judgment-gate", "pending"]
    assert autopilot_caps.main(argv) == 0
    res = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert res["proceed"] is True
    assert res["next_stage"] == "execute"
    assert res["judgment_auto_answered"] is True
    d = res["judgment_directive"]
    assert "write NO approval" in d
    assert "not a reason to stop" in d
    assert "when `proceed` is true" in d
