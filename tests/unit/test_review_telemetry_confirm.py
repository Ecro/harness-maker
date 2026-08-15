"""Phase 2 — AC-005 / AC-012: the confirmation + coverage record is self-identifying."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from harness_maker.conditional_router import MANDATORY_LENSES
from harness_maker.review_telemetry import ReviewTelemetryRecord

ALL_LENSES = list(MANDATORY_LENSES)


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ts": "2026-08-14T00:00:00Z",
        "slug": "ai-review-exit-criteria",
        "round": 1,
        "pass1_n": 3,
        "pass2_kept_n": 2,
        "consensus_passed_n": 1,
        "wall_time_ms": 1000,
        "build_break_count": 0,
        "auto_fix_reverted_n": 0,
    }
    base.update(overrides)
    return base


def _rejected_by_a_rule(**row: Any) -> list[dict[str, Any]]:
    """Assert the row is rejected, and that a RULE rejected it — not the extra-key guard.

    The model sets ``extra="forbid"``, so before the three fields exist EVERY row carrying
    them raises `ValidationError` for a reason unrelated to any rule. A bare
    ``pytest.raises(ValidationError)`` is therefore satisfied by an implementation that has
    none of these fields and none of these rules: it reads GREEN at the RED gate and stays
    green against a schema that ships the fields with no validator at all.

    Excluding ``extra_forbidden`` is what makes each assertion able to fail.
    """
    with pytest.raises(ValidationError) as excinfo:
        ReviewTelemetryRecord(**row)
    errors = excinfo.value.errors()
    assert errors, "ValidationError carried no errors"
    assert all(e["type"] != "extra_forbidden" for e in errors), (
        f"row was rejected by the extra-key guard, not by a rule: {errors}"
    )
    return errors


def _mentions(errors: list[dict[str, Any]], field: str) -> bool:
    return any(field in str(e.get("loc", ())) or field in str(e.get("msg", "")) for e in errors)


# ── rule 3: legacy rows keep parsing ──────────────────────────────────────────


def test_legacy_row_without_any_new_field_still_parses() -> None:
    """Rows written before this version must keep parsing — they are append-only."""
    record = ReviewTelemetryRecord(**_row(terminal=True))
    assert record.lenses_exercised is None
    assert record.confirm_pass_ran is None
    assert record.confirm_pass_new_severe_n is None


# ── rule 1: a row that identifies itself as new must be readable, both directions ──


def test_lenses_exercised_requires_confirm_pass_ran() -> None:
    errors = _rejected_by_a_rule(**_row(terminal=True, lenses_exercised=["robustness"]))
    assert _mentions(errors, "confirm_pass_ran"), errors


def test_confirm_pass_ran_requires_lenses_exercised() -> None:
    """The mirror direction — a row this version emits may not have a null coverage field.

    A one-way check (`lenses set and ran absent -> raise`) satisfies the other direction's
    test while accepting `{confirm_pass_ran: false, lenses_exercised: null}`: a new-version
    row indistinguishable from a legacy one, which is exactly what rule 1 forbids. Without
    this case that weaker implementation passes the whole file.
    """
    errors = _rejected_by_a_rule(**_row(terminal=True, confirm_pass_ran=False))
    assert _mentions(errors, "lenses_exercised"), errors


def test_all_lenses_failed_row_is_distinguishable_from_a_legacy_row() -> None:
    """The worst case must not be the one that looks like a pre-change row.

    A round in which every lens dispatch failed writes `[]`, not null.
    """
    record = ReviewTelemetryRecord(
        **_row(terminal=True, lenses_exercised=[], confirm_pass_ran=False)
    )
    assert record.lenses_exercised == []
    assert record.confirm_pass_ran is False
    assert record.confirm_pass_new_severe_n is None


# ── rule 2: the count is meaningful only when the pass ran ────────────────────


def test_count_is_required_when_the_pass_ran() -> None:
    errors = _rejected_by_a_rule(
        **_row(terminal=True, lenses_exercised=ALL_LENSES, confirm_pass_ran=True)
    )
    assert _mentions(errors, "confirm_pass_new_severe_n"), errors


def test_count_must_be_absent_when_the_pass_did_not_run() -> None:
    """A count beside "the pass did not run" has no meaning.

    This is the pair plain both-or-neither admitted.
    """
    errors = _rejected_by_a_rule(
        **_row(
            terminal=True,
            lenses_exercised=[],
            confirm_pass_ran=False,
            confirm_pass_new_severe_n=0,
        )
    )
    assert _mentions(errors, "confirm_pass_new_severe_n"), errors


# ── S4: the clean confirmation pass ───────────────────────────────────────────


def test_s4_clean_confirmation_row_is_accepted() -> None:
    record = ReviewTelemetryRecord(
        **_row(
            terminal=True,
            lenses_exercised=ALL_LENSES,
            confirm_pass_ran=True,
            confirm_pass_new_severe_n=0,
        )
    )
    assert record.confirm_pass_new_severe_n == 0
    assert record.lenses_exercised == ALL_LENSES


# ── rule 2 acceptance: a count the pass actually produced ─────────────────────


def test_dirty_confirmation_row_carries_a_nonzero_count() -> None:
    """Not an S4 case — S4's Then is zero new severe findings. This is a rule-2 acceptance.

    Load-bearing despite the demotion: it is the only positive count this file accepts, so
    without it an implementation that constrained `confirm_pass_new_severe_n` to the literal
    `0` would pass everything here.
    """
    record = ReviewTelemetryRecord(
        **_row(
            terminal=True,
            lenses_exercised=ALL_LENSES,
            confirm_pass_ran=True,
            confirm_pass_new_severe_n=2,
        )
    )
    assert record.confirm_pass_new_severe_n == 2


# ── S9: the non-approval exit records the pass as not-run ─────────────────────


def test_s9_terminal_row_records_the_pass_as_not_run() -> None:
    """S9's own row, which no other test constructs.

    A review that stops for `max_review_rounds` or the no-progress invariant did exercise
    its lenses but never dispatched a confirmation pass. That row must be accepted and must
    read as not-run — never as "ran and found nothing".
    """
    record = ReviewTelemetryRecord(
        **_row(terminal=True, lenses_exercised=ALL_LENSES, confirm_pass_ran=False)
    )
    assert record.confirm_pass_ran is False
    assert record.confirm_pass_new_severe_n is None
    assert record.lenses_exercised == ALL_LENSES


def test_non_terminal_round_row_carries_coverage_but_no_confirmation_count() -> None:
    """Coverage is per-round; the confirmation pass happens once, at the end."""
    record = ReviewTelemetryRecord(
        **_row(terminal=False, lenses_exercised=["robustness"], confirm_pass_ran=False)
    )
    assert record.terminal is False
    assert record.confirm_pass_new_severe_n is None


# ── field-level constraints ───────────────────────────────────────────────────


def test_unknown_lens_name_is_rejected() -> None:
    """`lenses_exercised` is the gate's input; an unrecognised name has no reading."""
    assert "not-a-lens" not in MANDATORY_LENSES
    errors = _rejected_by_a_rule(
        **_row(terminal=True, lenses_exercised=["not-a-lens"], confirm_pass_ran=False)
    )
    assert _mentions(errors, "lenses_exercised"), errors


def test_negative_severe_count_is_rejected() -> None:
    errors = _rejected_by_a_rule(
        **_row(
            terminal=True,
            lenses_exercised=ALL_LENSES,
            confirm_pass_ran=True,
            confirm_pass_new_severe_n=-1,
        )
    )
    assert any(e["type"] == "greater_than_equal" for e in errors), errors
