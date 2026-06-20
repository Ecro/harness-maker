"""P6 — boundary-check CLI + next_stage + ledger advanced-count (live auto-advance core)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from harness_maker import autopilot, autopilot_caps, autopilot_ledger
from harness_maker.models import AtomicStage

_PIPELINE = list(AtomicStage)  # research, spec, plan, execute, review, wrapup, verify
_STAGES = [s.value for s in _PIPELINE]


def _arm(root: Path, *, created: datetime) -> None:
    autopilot.write(root, level="auto_safe", pipeline=_PIPELINE, now=created.isoformat())


# ── next_stage helper ───────────────────────────────────────────────────────


def test_next_stage_middle() -> None:
    assert autopilot_caps.next_stage(_STAGES, "research") == "spec"
    assert autopilot_caps.next_stage(_STAGES, "review") == "wrapup"


def test_next_stage_last_is_none() -> None:
    assert autopilot_caps.next_stage(_STAGES, _STAGES[-1]) is None


def test_next_stage_unknown_is_none() -> None:
    assert autopilot_caps.next_stage(_STAGES, "not-a-stage") is None


# ── ledger advanced-count ───────────────────────────────────────────────────


def test_count_events_filters_by_type_and_since(tmp_path: Path) -> None:
    base = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    autopilot_ledger.append_event(tmp_path, event="advanced", now=base.isoformat())
    autopilot_ledger.append_event(tmp_path, event="halted_cap", now=base.isoformat())
    autopilot_ledger.append_event(
        tmp_path, event="advanced", now=(base + timedelta(minutes=5)).isoformat()
    )
    assert autopilot_ledger.count_events(tmp_path, "advanced") == 2
    assert autopilot_ledger.count_events(tmp_path, "halted_cap") == 1
    # since-filter: only the +5min advanced counts.
    assert (
        autopilot_ledger.count_events(
            tmp_path, "advanced", since=(base + timedelta(minutes=1)).isoformat()
        )
        == 1
    )


# ── boundary CLI ────────────────────────────────────────────────────────────


def test_boundary_proceeds_and_records_advance(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    # Fresh marker (live clock — the CLI reads real time; a fixed past created_at would
    # trip the time cap once the session runs long enough — determinism, checkpoint 7).
    _arm(tmp_path, created=datetime.now(UTC))
    rc = autopilot_caps.main(
        [
            "boundary",
            "--root",
            str(tmp_path),
            "--current",
            "research",
            "--step-cap",
            "20",
            "--time-cap-min",
            "60",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proceed"] is True
    assert out["next_stage"] == "spec"
    assert out["halt_kind"] is None
    # the authorized advance was recorded → one advanced event now on the ledger,
    # carrying the destination stage.
    assert autopilot_ledger.count_events(tmp_path, "advanced") == 1
    ledger = (tmp_path / ".claude" / "observability" / "auto-advance.jsonl").read_text()
    assert json.loads(ledger.splitlines()[-1])["to"] == "spec"


def test_boundary_step_cap_halt(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=now)
    # pre-seed the ledger to the cap.
    for _ in range(3):
        autopilot_ledger.append_event(tmp_path, event="advanced", now=now.isoformat())
    rc = autopilot_caps.main(
        [
            "boundary",
            "--root",
            str(tmp_path),
            "--current",
            "research",
            "--step-cap",
            "3",
            "--time-cap-min",
            "60",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proceed"] is False
    assert out["halt_kind"] == "step_cap"
    # halted_cap recorded; NO new advanced.
    assert autopilot_ledger.count_events(tmp_path, "halted_cap") == 1
    assert autopilot_ledger.count_events(tmp_path, "advanced") == 3


def test_boundary_time_cap_halt(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    created = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=created)
    # CLI uses the live clock; an old marker (created 90min ago, within 18h TTL) trips
    # a 30min time cap.
    created_old = datetime.now(UTC) - timedelta(minutes=90)
    autopilot.clear(tmp_path)
    _arm(tmp_path, created=created_old)
    rc = autopilot_caps.main(
        [
            "boundary",
            "--root",
            str(tmp_path),
            "--current",
            "research",
            "--step-cap",
            "20",
            "--time-cap-min",
            "30",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proceed"] is False
    assert out["halt_kind"] == "time_cap"


def test_boundary_kill_switch_no_marker(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    rc = autopilot_caps.main(
        [
            "boundary",
            "--root",
            str(tmp_path),
            "--current",
            "research",
            "--step-cap",
            "20",
            "--time-cap-min",
            "60",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proceed"] is False
    assert out["halt_kind"] == "kill_switch"


def test_boundary_unknown_current_preserves_marker(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    # An unknown --current (typo / stage outside the pipeline) must NOT be treated as
    # completion: marker preserved, distinct halt_kind (REVIEW P2).
    _arm(tmp_path, created=datetime.now(UTC))
    rc = autopilot_caps.main(
        [
            "boundary",
            "--root",
            str(tmp_path),
            "--current",
            "not-a-real-stage",
            "--step-cap",
            "20",
            "--time-cap-min",
            "60",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proceed"] is False
    assert out["halt_kind"] == "unknown_stage"
    assert out["pipeline_complete"] is False
    assert autopilot.load(tmp_path) is not None  # marker NOT cleared


def test_boundary_pipeline_complete_clears_marker(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    _arm(tmp_path, created=datetime.now(UTC))  # fresh marker (live-clock CLI — see above)
    rc = autopilot_caps.main(
        [
            "boundary",
            "--root",
            str(tmp_path),
            "--current",
            _STAGES[-1],
            "--step-cap",
            "20",
            "--time-cap-min",
            "60",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proceed"] is False
    assert out["pipeline_complete"] is True
    assert out["next_stage"] is None
    # final stage clears the marker (ADR-006).
    assert autopilot.load(tmp_path) is None
