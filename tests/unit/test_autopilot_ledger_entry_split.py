"""PLAN-autopilot-advance-noop Phase 2 — `advance_authorized` / `advance_entered` split.

ADR-004  the ledger records authorization and entry separately; the step cap counts
         entries. A legacy `advanced` row counts as an entry ONLY outside the current
         marker window (a mid-window upgrade would otherwise double-count one advance).
ADR-005  entry is confirmed retroactively via greedy in-order pairing.

Why this file exists at all: before the split, `_cmd_boundary` appended `advanced`
BEFORE the model acted, so the ledger recorded every authorization as a success and
could not distinguish "announced but stalled" from "actually advanced". That is why the
reported bug survived undetected.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from harness_maker import autopilot_ledger

WINDOW_START = "2026-07-31T10:00:00.000000+00:00"


def _ts(minutes: float) -> str:
    base = datetime(2026, 7, 31, 10, 0, 0, tzinfo=UTC)
    return (base + timedelta(minutes=minutes)).isoformat()


def _rows(root: Path) -> list[dict[str, object]]:
    p = autopilot_ledger.ledger_path(root)
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _emit(root: Path, event: str, *, ts: str, **fields: object) -> None:
    autopilot_ledger.append_event(root, event=event, fields=fields, now=ts)  # type: ignore[arg-type]


# --- vocabulary -----------------------------------------------------------------


def test_new_events_are_accepted_and_legacy_survives() -> None:
    assert "advance_authorized" in autopilot_ledger.EVENTS
    assert "advance_entered" in autopilot_ledger.EVENTS
    assert "advanced" in autopilot_ledger.EVENTS, "legacy value stays readable for history"


def test_vocabulary_stays_disjoint_from_iter_receipt_verdicts() -> None:
    """ADR-009's structural invariant must survive the extension."""
    from typing import get_args

    from harness_maker.iter_receipts import Verdict

    assert autopilot_ledger.EVENTS.isdisjoint(get_args(Verdict))


# --- ADR-005: greedy in-order pairing -------------------------------------------


def test_pairs_a_single_authorization(tmp_path: Path) -> None:
    _emit(tmp_path, "advance_authorized", ts=_ts(1), to="spec")
    found = autopilot_ledger.find_unconfirmed_authorization(tmp_path, to="spec", since=WINDOW_START)
    assert found is not None
    assert found["ts"] == _ts(1)


def test_returns_none_when_already_confirmed(tmp_path: Path) -> None:
    _emit(tmp_path, "advance_authorized", ts=_ts(1), to="spec")
    _emit(tmp_path, "advance_entered", ts=_ts(2), to="spec", elapsed_s=60.0)
    assert (
        autopilot_ledger.find_unconfirmed_authorization(tmp_path, to="spec", since=WINDOW_START)
        is None
    )


def test_repeated_cycle_pairs_oldest_to_oldest(tmp_path: Path) -> None:
    """review→execute→review: a stage can be authorized and entered more than once."""
    _emit(tmp_path, "advance_authorized", ts=_ts(1), to="review")
    _emit(tmp_path, "advance_entered", ts=_ts(2), to="review", elapsed_s=60.0)
    _emit(tmp_path, "advance_authorized", ts=_ts(5), to="review")
    found = autopilot_ledger.find_unconfirmed_authorization(
        tmp_path, to="review", since=WINDOW_START
    )
    assert found is not None
    assert found["ts"] == _ts(5), "the FIRST authorization is already paired"


def test_entry_never_pairs_an_authorization_that_follows_it(tmp_path: Path) -> None:
    """An entry at t=2 cannot confirm an authorization issued at t=5."""
    _emit(tmp_path, "advance_entered", ts=_ts(2), to="spec", elapsed_s=1.0)
    _emit(tmp_path, "advance_authorized", ts=_ts(5), to="spec")
    found = autopilot_ledger.find_unconfirmed_authorization(tmp_path, to="spec", since=WINDOW_START)
    assert found is not None
    assert found["ts"] == _ts(5)


def test_other_stages_do_not_confirm(tmp_path: Path) -> None:
    _emit(tmp_path, "advance_authorized", ts=_ts(1), to="spec")
    _emit(tmp_path, "advance_entered", ts=_ts(2), to="plan", elapsed_s=60.0)
    assert (
        autopilot_ledger.find_unconfirmed_authorization(tmp_path, to="spec", since=WINDOW_START)
        is not None
    )


def test_authorization_before_the_window_is_ignored(tmp_path: Path) -> None:
    _emit(tmp_path, "advance_authorized", ts=_ts(-120), to="spec")
    assert (
        autopilot_ledger.find_unconfirmed_authorization(tmp_path, to="spec", since=WINDOW_START)
        is None
    )


def test_no_ledger_file_is_not_an_error(tmp_path: Path) -> None:
    assert (
        autopilot_ledger.find_unconfirmed_authorization(tmp_path, to="spec", since=WINDOW_START)
        is None
    )


# --- ADR-004: step-count window rule --------------------------------------------


def test_legacy_advanced_outside_window_counts_as_entry(tmp_path: Path) -> None:
    _emit(tmp_path, "advanced", ts=_ts(-120), to="spec")
    assert autopilot_ledger.count_entries(tmp_path, since=None) == 1


def test_legacy_rows_before_the_upgrade_point_still_count(tmp_path: Path) -> None:
    """Mid-window upgrade — REVISED after review (k-of-4: codex P2, antigravity P1,
    code-reviewer P2 all flagged the original rule).

    The first draft dropped every legacy row once any new-vocabulary row appeared, to avoid
    double-counting a phantom. That handed a partially-consumed session a fresh step
    budget: `advanced(spec)` + `advanced(plan)` + a stalled `advance_authorized(execute)`
    counted as ZERO, so the runaway cap reset. Under-counting lets the chain run LONGER
    than configured, which is the unsafe direction; over-counting fires the cap early. The
    rule now sums legacy rows up to the upgrade point.
    """
    _emit(tmp_path, "advanced", ts=_ts(1), to="spec")
    _emit(tmp_path, "advanced", ts=_ts(2), to="plan")
    _emit(tmp_path, "advance_authorized", ts=_ts(5), to="execute")  # authorized, stalled
    assert autopilot_ledger.count_entries(tmp_path, since=WINDOW_START) == 2


def test_a_pre_upgrade_phantom_over_counts_rather_than_under_counts(tmp_path: Path) -> None:
    """The accepted cost of the rule above, pinned so the trade-off stays visible.

    A phantom `advanced` (written before the model acted — the defect the split fixes)
    followed by the re-done new-vocabulary pair for the SAME stage counts 2 for one
    physical advance. The cap fires one step early: bounded, and the safe direction.
    """
    _emit(tmp_path, "advanced", ts=_ts(1), to="spec")  # phantom: announced, stalled
    _emit(tmp_path, "advance_authorized", ts=_ts(5), to="spec")
    _emit(tmp_path, "advance_entered", ts=_ts(6), to="spec", elapsed_s=60.0)
    assert autopilot_ledger.count_entries(tmp_path, since=WINDOW_START) == 2


def test_legacy_rows_after_the_upgrade_point_are_ignored(tmp_path: Path) -> None:
    """New code never writes `advanced`, so a legacy row appearing after the upgrade point
    is not a real step — it can only be a hand-edited or replayed ledger."""
    _emit(tmp_path, "advance_authorized", ts=_ts(1), to="spec")
    _emit(tmp_path, "advance_entered", ts=_ts(2), to="spec", elapsed_s=60.0)
    _emit(tmp_path, "advanced", ts=_ts(5), to="plan")
    assert autopilot_ledger.count_entries(tmp_path, since=WINDOW_START) == 1


def test_legacy_only_window_still_counts(tmp_path: Path) -> None:
    """A window with NO new-vocabulary rows keeps the legacy reading — continuity."""
    _emit(tmp_path, "advanced", ts=_ts(1), to="spec")
    _emit(tmp_path, "advanced", ts=_ts(2), to="plan")
    assert autopilot_ledger.count_entries(tmp_path, since=WINDOW_START) == 2


def test_entries_are_counted_not_authorizations(tmp_path: Path) -> None:
    _emit(tmp_path, "advance_authorized", ts=_ts(1), to="spec")
    _emit(tmp_path, "advance_authorized", ts=_ts(2), to="plan")
    _emit(tmp_path, "advance_entered", ts=_ts(3), to="spec", elapsed_s=120.0)
    assert autopilot_ledger.count_entries(tmp_path, since=WINDOW_START) == 1


# --- smoke denominator ----------------------------------------------------------


def test_smoke_counts_the_new_events(tmp_path: Path) -> None:
    _emit(tmp_path, "advance_authorized", ts=_ts(1), to="spec")
    out = autopilot_ledger.smoke_check(tmp_path, yaml_level="auto_safe")
    assert out["degraded"] is False
    assert out["entry_count"] >= 1


def test_smoke_still_flags_an_empty_ledger(tmp_path: Path) -> None:
    out = autopilot_ledger.smoke_check(tmp_path, yaml_level="auto_safe")
    assert out["degraded"] is True


def test_append_still_rejects_a_verdict_literal(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError, match="not in"):
        autopilot_ledger.append_event(tmp_path, event="pass", fields={})  # type: ignore[arg-type]
    assert _rows(tmp_path) == []
