"""PLAN-autopilot-advance-noop Phase 3 — boundary/gate-blocked wiring.

The regression gate that matters most here is
`test_no_marker_appends_zero_rows`: the retro-confirm must sit AFTER the
`active_marker` check. Placed before it, every manual autopilot-off run would append an
`advance_entered` row, polluting both the `/hm:health` smoke denominator and the step-cap
numerator — the P2-5 invariant `autopilot_caps.py` already carries for `gate_blocked`.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from harness_maker import autopilot, autopilot_caps, autopilot_ledger
from harness_maker.models import AtomicStage

PIPELINE = [AtomicStage.RESEARCH, AtomicStage.SPEC, AtomicStage.PLAN, AtomicStage.EXECUTE]


@pytest.fixture(autouse=True)
def _session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HM_SESSION_ID", "sess-A")


def _arm(root: Path) -> None:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(root, level="auto_safe", pipeline=PIPELINE)


def _boundary(root: Path, current: str, *extra: str) -> dict[str, object]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = autopilot_caps.main(["boundary", "--root", str(root), "--current", current, *extra])
    assert rc == 0
    value: dict[str, object] = json.loads(buf.getvalue().strip())
    return value


def _events(root: Path) -> list[tuple[str, object]]:
    p = autopilot_ledger.ledger_path(root)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out.append((r["event"], r.get("to") or r.get("stage")))
    return out


# --- ADR-004/005: the authorize → enter cycle -----------------------------------


def test_chain_records_authorized_then_entered(tmp_path: Path) -> None:
    _arm(tmp_path)
    first = _boundary(tmp_path, "research", "--slug", "s")
    assert first["proceed"] is True
    assert first["next_stage"] == "spec"
    assert _events(tmp_path) == [("advance_authorized", "spec")]

    second = _boundary(tmp_path, "spec", "--slug", "s")
    assert second["next_stage"] == "plan"
    assert _events(tmp_path) == [
        ("advance_authorized", "spec"),
        ("advance_entered", "spec"),
        ("advance_authorized", "plan"),
    ]


def test_entered_row_carries_elapsed_s(tmp_path: Path) -> None:
    _arm(tmp_path)
    _boundary(tmp_path, "research", "--slug", "s")
    _boundary(tmp_path, "spec", "--slug", "s")
    rows = [
        json.loads(x)
        for x in autopilot_ledger.ledger_path(tmp_path).read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    entered = next(r for r in rows if r["event"] == "advance_entered")
    assert isinstance(entered["elapsed_s"], float)
    assert entered["elapsed_s"] >= 0.0


def test_no_marker_appends_zero_rows(tmp_path: Path) -> None:
    """ADR-005 placement — the P2-5 phantom-row invariant, for BOTH subcommands."""
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    out = _boundary(tmp_path, "spec")
    assert out["halt_kind"] == "kill_switch"
    assert autopilot_caps.main(["gate-blocked", "--root", str(tmp_path), "--stage", "spec"]) == 0
    assert _events(tmp_path) == []


def test_gate_blocked_also_confirms_entry(tmp_path: Path) -> None:
    _arm(tmp_path)
    _boundary(tmp_path, "research", "--slug", "s")
    autopilot_caps.main(["gate-blocked", "--root", str(tmp_path), "--stage", "spec"])
    assert _events(tmp_path) == [
        ("advance_authorized", "spec"),
        ("advance_entered", "spec"),
        ("gate_blocked", "spec"),
    ]


def test_entry_is_confirmed_only_once(tmp_path: Path) -> None:
    _arm(tmp_path)
    _boundary(tmp_path, "research", "--slug", "s")
    _boundary(tmp_path, "spec", "--slug", "s")
    autopilot_caps.main(["gate-blocked", "--root", str(tmp_path), "--stage", "spec"])
    entered = [e for e in _events(tmp_path) if e[0] == "advance_entered" and e[1] == "spec"]
    assert len(entered) == 1


def test_step_cap_counts_entries_not_authorizations(tmp_path: Path) -> None:
    _arm(tmp_path)
    # research → spec authorizes but the chain never enters spec.
    first = _boundary(tmp_path, "research", "--slug", "s", "--step-cap", "1")
    assert first["proceed"] is True
    assert first["steps"] == 1, "the authorization it just granted counts toward the cap"
    # Re-running research: still ZERO entries, so the cap has not been consumed by a
    # stage that never ran.
    again = _boundary(tmp_path, "research", "--slug", "s", "--step-cap", "1")
    assert again["proceed"] is True


def test_step_cap_fires_once_entries_accumulate(tmp_path: Path) -> None:
    _arm(tmp_path)
    _boundary(tmp_path, "research", "--slug", "s")
    _boundary(tmp_path, "spec", "--slug", "s")  # 1 entry recorded
    blocked = _boundary(tmp_path, "plan", "--slug", "s", "--step-cap", "1")
    assert blocked["proceed"] is False
    assert blocked["halt_kind"] == "step_cap"


# --- ADR-003: slug propagation --------------------------------------------------


def test_boundary_echoes_flag_slug_and_persists_it(tmp_path: Path) -> None:
    _arm(tmp_path)
    out = _boundary(tmp_path, "research", "--slug", "my-task")
    assert out["task_slug"] == "my-task"
    assert out["task_slug_source"] == "flag"
    marker = autopilot.active_marker(tmp_path)
    assert marker is not None
    assert marker.task_slug == "my-task"
    assert marker.task_slug_stage == "research"


def test_persisted_slug_is_reported_as_persisted(tmp_path: Path) -> None:
    """The fallback must be attributable — a silent inherited slug is the failure mode
    ADR-003 rejects slug inference over."""
    _arm(tmp_path)
    _boundary(tmp_path, "research", "--slug", "my-task")
    out = _boundary(tmp_path, "spec")  # flag omitted
    assert out["task_slug"] == "my-task"
    assert out["task_slug_source"] == "persisted"


def test_absent_slug_is_null_not_empty_string(tmp_path: Path) -> None:
    _arm(tmp_path)
    out = _boundary(tmp_path, "research")
    assert out["task_slug"] is None
    assert out["task_slug_source"] is None


# --- unchanged terminal paths ---------------------------------------------------


def test_merge_gate_still_stops_before_wrapup(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=[AtomicStage.VERIFY, AtomicStage.WRAPUP])
    out = _boundary(tmp_path, "verify", "--slug", "s")
    assert out["proceed"] is False
    assert out["halt_kind"] == "merge_gate"
    assert autopilot.load(tmp_path, session_id=None) is None, (
        "marker cleared so the Stop-hook stands down"
    )


def test_pipeline_complete_clears_marker(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    autopilot.write(tmp_path, level="auto_safe", pipeline=[AtomicStage.RESEARCH])
    out = _boundary(tmp_path, "research", "--slug", "s")
    assert out["pipeline_complete"] is True
    assert autopilot.load(tmp_path, session_id=None) is None


def test_unknown_stage_preserves_marker_and_writes_nothing(tmp_path: Path) -> None:
    _arm(tmp_path)
    out = _boundary(tmp_path, "bogus")
    assert out["halt_kind"] == "unknown_stage"
    assert autopilot.load(tmp_path, session_id=None) is not None
    assert _events(tmp_path) == []
