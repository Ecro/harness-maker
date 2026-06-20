"""P8 e2e — the mechanical auto-advance chain end-to-end (durable form of the P0 spike).

The LIVE chain (a stage prose-invoking `Skill(hm:<next>)` mid-turn) is a Claude-runtime
behavior that pytest cannot drive — it is verified manually (P0 spike + the cross-IDE
manual checklist). What IS automatable, and what this asserts, is the DETERMINISTIC spine
the live chain rests on: armed marker → `boundary` authorizes each step + records an
`advanced` event + reports the next stage → last stage clears the marker + reports
pipeline_complete. A regression here breaks live auto-advance even if the prose is perfect.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from harness_maker import autopilot, autopilot_caps, autopilot_ledger
from harness_maker.models import AtomicStage

_PIPELINE = list(AtomicStage)
_STAGES = [s.value for s in _PIPELINE]


def _boundary(root: Path, current: str, capsys) -> dict:  # noqa: ANN001
    rc = autopilot_caps.main(
        [
            "boundary",
            "--root",
            str(root),
            "--current",
            current,
            "--step-cap",
            "50",
            "--time-cap-min",
            "600",
        ]
    )
    assert rc == 0
    return json.loads(capsys.readouterr().out)


def test_full_pipeline_chain_advances_then_completes(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    # Arm a fresh autopilot session over the full default pipeline.
    autopilot.write(
        tmp_path, level="auto_safe", pipeline=_PIPELINE, now=datetime.now(UTC).isoformat()
    )

    # Walk every non-terminal boundary: each authorizes an advance to the NEXT stage.
    for i, stage in enumerate(_STAGES[:-1]):
        out = _boundary(tmp_path, stage, capsys)
        assert out["proceed"] is True, f"{stage} should advance"
        assert out["next_stage"] == _STAGES[i + 1]
        assert out["halt_kind"] is None
        assert out["pipeline_complete"] is False

    # The chain recorded exactly one `advanced` event per advance (steps - 1).
    assert autopilot_ledger.count_events(tmp_path, "advanced") == len(_STAGES) - 1
    # The marker is still live mid-chain.
    assert autopilot.load(tmp_path) is not None

    # The terminal boundary completes the pipeline + clears the marker (ADR-006).
    final = _boundary(tmp_path, _STAGES[-1], capsys)
    assert final["proceed"] is False
    assert final["pipeline_complete"] is True
    assert final["next_stage"] is None
    assert autopilot.load(tmp_path) is None  # session ended


def test_chain_halts_at_step_cap(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    # A low step cap stops the chain mid-pipeline with a halted_cap receipt (runaway guard).
    # Deterministic on the live clock: a generous time cap (600 min) guarantees the STEP cap
    # fires first (evaluate_boundary order: kill_switch → step_cap → time_cap), so the
    # outcome never depends on real elapsed time.
    autopilot.write(
        tmp_path, level="auto_safe", pipeline=_PIPELINE, now=datetime.now(UTC).isoformat()
    )
    cap = 2
    advanced = 0
    for stage in _STAGES[:-1]:
        rc = autopilot_caps.main(
            [
                "boundary",
                "--root",
                str(tmp_path),
                "--current",
                stage,
                "--step-cap",
                str(cap),
                "--time-cap-min",
                "600",
            ]
        )
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        if out["proceed"]:
            advanced += 1
        else:
            assert out["halt_kind"] == "step_cap"
            break
    assert advanced == cap  # advanced exactly `cap` times, then the cap fired
    assert autopilot_ledger.count_events(tmp_path, "halted_cap") == 1
