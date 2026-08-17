"""P7 — gate_blocked ledger call-site + /hm:health auto-advance smoke + ADR-009 regression."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from harness_maker import autopilot, autopilot_caps, autopilot_ledger
from harness_maker.iter_receipts import Verdict
from harness_maker.models import AtomicStage


def _ledger_lines(root: Path) -> list[dict[str, Any]]:
    path = root / ".claude" / "observability" / "auto-advance.jsonl"
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


# ── gate_blocked call-site (autopilot_caps gate-blocked CLI) ─────────────────


def test_gate_blocked_cli_appends_event(tmp_path: Path) -> None:
    # P2-5: gate-blocked records ONLY for a live autopilot session → arm a marker first.
    autopilot.write(tmp_path, level="auto_safe", pipeline=list(AtomicStage))
    rc = autopilot_caps.main(["gate-blocked", "--root", str(tmp_path), "--stage", "review"])
    assert rc == 0
    lines = _ledger_lines(tmp_path)
    assert len(lines) == 1
    assert lines[0]["event"] == "gate_blocked"
    assert lines[0]["stage"] == "review"


def test_gate_blocked_cli_noop_without_active_marker(tmp_path: Path) -> None:
    # P2-5: no marker (off / foreign / stale) → no phantom gate_blocked row that would
    # pollute the audit trail + smoke denominator.
    rc = autopilot_caps.main(["gate-blocked", "--root", str(tmp_path), "--stage", "review"])
    assert rc == 0
    assert _ledger_lines(tmp_path) == []


def test_count_events_counts_unparseable_ts_in_window(tmp_path: Path) -> None:
    # P2-4: a row with a missing/garbage ts must be COUNTED on the `since` path (in-window)
    # — dropping it would under-count `advanced` and delay the runaway step cap.
    base = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    autopilot_ledger.append_event(tmp_path, event="advanced", now="not-a-timestamp")
    autopilot_ledger.append_event(tmp_path, event="advanced", now=base.isoformat())
    since = (base - timedelta(minutes=1)).isoformat()
    # both count: the parseable one is after `since`, the garbage-ts one is kept block-biased.
    assert autopilot_ledger.count_events(tmp_path, "advanced", since=since) == 2


def test_ledger_rejects_oversized_line(tmp_path: Path) -> None:
    # P3: the PIPE_BUF/4096 append-atomicity guard must reject an oversized line (the
    # concurrent-writer atomicity guarantee depends on it).
    with pytest.raises(ValueError, match="PIPE_BUF"):
        autopilot_ledger.append_event(tmp_path, event="advanced", fields={"big": "x" * 5000})


# ── /hm:health smoke (autopilot_ledger.smoke_check) ─────────────────────────


def test_smoke_degraded_when_enabled_but_empty(tmp_path: Path) -> None:
    # autonomy configured (non-gated) but the ledger has zero entries → degradation.
    result = autopilot_ledger.smoke_check(tmp_path, yaml_level="auto_safe")
    assert result["degraded"] is True
    assert result["entry_count"] == 0


def test_smoke_unknown_level_not_degraded(tmp_path: Path) -> None:
    # An unknown/garbage level (typo, pre-feature default) is treated as not-armed → no
    # false 'never fired' alarm (REVIEW P1; mirrors effective_level's clamp-to-gated).
    result = autopilot_ledger.smoke_check(tmp_path, yaml_level="off")
    assert result["degraded"] is False


def test_smoke_not_degraded_when_gated(tmp_path: Path) -> None:
    # gated (default) → autopilot intentionally off → no degradation signal.
    result = autopilot_ledger.smoke_check(tmp_path, yaml_level="gated")
    assert result["degraded"] is False


def test_smoke_not_degraded_when_entries_exist(tmp_path: Path) -> None:
    autopilot_ledger.append_event(tmp_path, event="advanced", fields={"to": "spec"})
    result = autopilot_ledger.smoke_check(tmp_path, yaml_level="full")
    assert result["degraded"] is False
    assert result["entry_count"] == 1


def test_smoke_cli_emits_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = autopilot_ledger.main(["smoke", "--root", str(tmp_path), "--level", "auto_safe"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["degraded"] is True
    assert out["level"] == "auto_safe"
    assert set(out) == {"degraded", "level", "entry_count", "reason"}  # full surface locked


# ── ADR-009 collision regression (runtime, not just the type-level disjoint check) ──


def test_ledger_never_writes_a_verdict_literal_in_event(tmp_path: Path) -> None:
    # Write every legal event; assert NO emitted `event` field is an iter_receipts.Verdict
    # literal (the two enums are disjoint by construction — this guards the on-disk bytes).
    for ev in ("advanced", "gate_blocked", "halted_cap"):
        autopilot_ledger.append_event(tmp_path, event=ev)
    verdicts = set(Verdict.__args__)  # type: ignore[attr-defined]
    events_on_disk = {ln["event"] for ln in _ledger_lines(tmp_path)}
    assert events_on_disk.isdisjoint(verdicts)
    # and the forbidden literals are still rejected at the write boundary.
    for forbidden in verdicts:
        with pytest.raises(ValueError, match="ADR-009"):
            autopilot_ledger.append_event(tmp_path, event=forbidden)
