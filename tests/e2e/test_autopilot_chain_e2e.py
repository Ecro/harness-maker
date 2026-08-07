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
from harness_maker.models import AutonomyConfig

# Use the CANONICAL default pipeline (verify BEFORE wrapup) — NOT list(AtomicStage), whose
# enum order puts wrapup first and would run verify after the commit (REVIEW P1-4).
_PIPELINE = list(AutonomyConfig().pipeline)
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


def test_full_pipeline_chain_advances_then_stops_before_wrapup(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    # Arm a fresh autopilot session over the full default pipeline (…review, verify, wrapup).
    autopilot.write(
        tmp_path, level="auto_safe", pipeline=_PIPELINE, now=datetime.now(UTC).isoformat()
    )

    # The auto-chain advances research → … → verify (every two-way-door boundary), but the
    # NEXT stage after verify is the human-gated `wrapup` (P1-1) — so the chain stops there.
    advancing = _STAGES[: _STAGES.index("verify")]  # research..review (proceed to the one after)
    for i, stage in enumerate(advancing):
        out = _boundary(tmp_path, stage, capsys)
        assert out["proceed"] is True, f"{stage} should advance"
        assert out["next_stage"] == _STAGES[i + 1]
        assert out["halt_kind"] is None

    # verify's boundary refuses to auto-enter wrapup → merge_gate stop + marker cleared.
    gate = _boundary(tmp_path, "verify", capsys)
    assert gate["proceed"] is False
    assert gate["halt_kind"] == "merge_gate"
    assert gate["next_stage"] == "wrapup"
    assert autopilot_ledger.count_events(tmp_path, "gate_blocked") == 1
    # One AUTHORIZATION per boundary that proceeded (research..review → verify), none into
    # wrapup. The legacy `advanced` event is retired: it was written before the model acted,
    # so it recorded permission as progress and could not distinguish "announced but
    # stalled" from a real advance (PLAN-autopilot-advance-noop ADR-004).
    assert autopilot_ledger.count_events(tmp_path, "advance_authorized") == len(advancing)
    assert autopilot_ledger.count_events(tmp_path, "advanced") == 0
    # Each stage's own boundary call retro-confirms the entry its predecessor authorized.
    # `research` was never authorized (it started the chain) so its call confirms nothing,
    # but `verify`'s gate call confirms the last one — the two counts coincide at
    # len(advancing) rather than differing by one.
    assert autopilot_ledger.count_events(tmp_path, "advance_entered") == len(advancing)
    # the session ended at the merge gate — wrapup is never auto-run.
    assert autopilot.load(tmp_path, session_id=None) is None


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
