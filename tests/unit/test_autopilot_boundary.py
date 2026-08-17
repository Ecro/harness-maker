"""P6 — boundary-check CLI + next_stage + ledger advanced-count (live auto-advance core)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker import autopilot, autopilot_caps, autopilot_ledger
from harness_maker.models import AutonomyConfig

# Canonical default order (verify BEFORE wrapup) — one source of truth with the e2e +
# autonomy_config tests, NOT list(AtomicStage) whose enum order the P1-4 fix declared wrong.
_PIPELINE = list(AutonomyConfig().pipeline)
_STAGES = [s.value for s in _PIPELINE]


def _arm(root: Path, *, created: datetime) -> None:
    autopilot.write(root, level="auto_safe", pipeline=_PIPELINE, now=created.isoformat())


# ── next_stage helper ───────────────────────────────────────────────────────


def test_next_stage_middle() -> None:
    assert autopilot_caps.next_stage(_STAGES, "research") == "spec"
    # canonical order: verify comes before wrapup.
    assert autopilot_caps.next_stage(_STAGES, "review") == "verify"


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


def test_boundary_proceeds_and_records_advance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    # The authorization was recorded — `advance_authorized`, NOT `advanced`
    # (PLAN-autopilot-advance-noop ADR-004). The old event conflated permission with
    # progress, which is why "announces but never advances" was invisible to this ledger.
    # Entry is confirmed later, by the NEXT stage's own boundary call.
    assert autopilot_ledger.count_events(tmp_path, "advance_authorized") == 1
    assert autopilot_ledger.count_events(tmp_path, "advanced") == 0
    assert autopilot_ledger.count_entries(tmp_path) == 0, "authorized ≠ entered"
    ledger = (tmp_path / ".claude" / "observability" / "auto-advance.jsonl").read_text()
    assert json.loads(ledger.splitlines()[-1])["to"] == "spec"


def test_boundary_step_cap_halt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # The boundary CLI checks the marker against the LIVE clock (18h TTL), so the
    # marker + its ledger events must be NOW, not a fixed past date — a hardcoded
    # 2026-06-20 marker rotted to stale→kill_switch after 18h (same live-clock fix
    # the time_cap test already uses).
    now = datetime.now(UTC)
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


def test_boundary_time_cap_halt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    created = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=created)
    # CLI uses the live clock; an old marker (created 90min ago, within 18h TTL) trips
    # a 30min time cap.
    created_old = datetime.now(UTC) - timedelta(minutes=90)
    autopilot.clear(tmp_path, session_id=None)
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


def test_boundary_kill_switch_no_marker(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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


def test_boundary_unknown_current_preserves_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    assert autopilot.load(tmp_path, session_id=None) is not None  # marker NOT cleared


def test_boundary_stops_before_wrapup_merge_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # P1-1: the chain must NEVER auto-enter wrapup (its Step 7.7 squash-land is a one-way
    # door). At the verify→wrapup boundary it stops with halt_kind=merge_gate, records a
    # gate_blocked event, clears the marker (Stop-hook stands down → human takes over), and
    # records NO advance.
    autopilot.write(
        tmp_path, level="auto_safe", pipeline=_PIPELINE, now=datetime.now(UTC).isoformat()
    )
    rc = autopilot_caps.main(
        ["boundary", "--root", str(tmp_path), "--current", "verify",
         "--step-cap", "20", "--time-cap-min", "60"]
    )  # fmt: skip
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proceed"] is False
    assert out["halt_kind"] == "merge_gate"
    assert out["next_stage"] == "wrapup"
    assert (
        autopilot.load(tmp_path, session_id=None) is None
    )  # marker cleared → backstop stands down
    assert autopilot_ledger.count_events(tmp_path, "gate_blocked") == 1
    assert autopilot_ledger.count_events(tmp_path, "advanced") == 0


def test_boundary_step_cap_clears_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # P2-6 / P3: a cap halt is TERMINAL → the marker is cleared so a later boundary call
    # cannot re-fire a duplicate halted_cap (and the Stop-hook stands down).
    now = datetime.now(UTC)
    _arm(tmp_path, created=now)
    for _ in range(3):
        autopilot_ledger.append_event(tmp_path, event="advanced", now=now.isoformat())
    rc = autopilot_caps.main(
        ["boundary", "--root", str(tmp_path), "--current", "research",
         "--step-cap", "3", "--time-cap-min", "60"]
    )  # fmt: skip
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["halt_kind"] == "step_cap"
    assert autopilot.load(tmp_path, session_id=None) is None  # cleared
    # a second call now sees kill_switch (no marker) → NO new halted_cap.
    autopilot_caps.main(
        ["boundary", "--root", str(tmp_path), "--current", "research",
         "--step-cap", "3", "--time-cap-min", "60"]
    )  # fmt: skip
    capsys.readouterr()
    assert autopilot_ledger.count_events(tmp_path, "halted_cap") == 1


def test_count_events_includes_exact_since_boundary(tmp_path: Path) -> None:
    # P3: ts == since must be INCLUDED (the same-second under-count the _utc_now_iso fix
    # addressed — the filter is `>= since`, not `> since`), AND a legacy 'Z'-form row on
    # disk still compares correctly against an isoformat `since` (mixed-format normalize).
    base = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    autopilot_ledger.append_event(tmp_path, event="advanced", now=base.isoformat())
    assert autopilot_ledger.count_events(tmp_path, "advanced", since=base.isoformat()) == 1
    autopilot_ledger.append_event(tmp_path, event="advanced", now="2026-06-20T12:00:00Z")
    assert (
        autopilot_ledger.count_events(tmp_path, "advanced", since="2026-06-20T12:00:00+00:00") == 2
    )


def test_boundary_pipeline_complete_clears_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    assert autopilot.load(tmp_path, session_id=None) is None
