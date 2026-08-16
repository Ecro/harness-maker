"""Phase 5 — the churn record on the telemetry row is readable in every state.

The rows are append-only, so an incoherent one is permanent. Each rejection below
names the wrong row it forbids, and every `pytest.raises` excludes
`extra_forbidden` — without that exclusion the assertions pass against a schema
that ships none of these fields, which is the RED gate reading green.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from harness_maker.review_churn import ChurnMeasurement, FileChurn, measure
from harness_maker.review_telemetry import ReviewTelemetryRecord


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ts": "2026-08-16T00:00:00Z",
        "slug": "review-loop-empirics",
        "round": 2,
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
    with pytest.raises(ValidationError) as excinfo:
        ReviewTelemetryRecord(**row)
    errors = [e for e in excinfo.value.errors() if e["type"] != "extra_forbidden"]
    assert errors, "rejected only by the extra-key guard — the rule does not exist"
    return errors


def test_legacy_row_without_any_churn_field_stays_valid() -> None:
    rec = ReviewTelemetryRecord(**_row())
    assert rec.churn_ratio is None
    assert rec.churn_measured_n is None


def test_measured_round_carries_ratio_and_counts() -> None:
    rec = ReviewTelemetryRecord(
        **_row(
            churn_ratio=0.35,
            churn_max_path="src/x.py",
            churn_measured_n=2,
            churn_excluded_n=1,
        )
    )
    assert rec.churn_ratio == 0.35


def test_binary_only_round_is_distinguishable_from_a_legacy_row() -> None:
    """Measured nothing, and says so — the case a nullable ratio alone loses."""
    rec = ReviewTelemetryRecord(**_row(churn_measured_n=0, churn_excluded_n=3))
    assert rec.churn_ratio is None
    assert rec.churn_measured_n == 0


def test_counts_are_both_or_neither() -> None:
    _rejected_by_a_rule(**_row(churn_measured_n=1, churn_ratio=0.5, churn_max_path="a"))


def test_ratio_without_counts_is_rejected() -> None:
    _rejected_by_a_rule(**_row(churn_ratio=0.5, churn_max_path="a"))


def test_measured_files_with_null_ratio_is_rejected() -> None:
    """A measured file always yields a number; the pair contradicts itself."""
    _rejected_by_a_rule(**_row(churn_measured_n=2, churn_excluded_n=0))


def test_zero_measured_with_a_ratio_is_rejected() -> None:
    _rejected_by_a_rule(
        **_row(churn_measured_n=0, churn_excluded_n=1, churn_ratio=0.4, churn_max_path="a")
    )


def test_ratio_without_its_path_is_rejected() -> None:
    _rejected_by_a_rule(**_row(churn_measured_n=1, churn_excluded_n=0, churn_ratio=0.4))


def test_out_of_range_ratio_is_rejected() -> None:
    _rejected_by_a_rule(
        **_row(churn_measured_n=1, churn_excluded_n=0, churn_ratio=1.5, churn_max_path="a")
    )


def test_measurement_as_record_validates_against_the_row() -> None:
    """The producer's output is accepted by the consumer's schema, unmodified.

    Asserting the two shapes separately would let them drift; this is the seam.
    """
    result = measure(
        [
            FileChurn("small.py", "modified", added=30, deleted=30, post_loc=30),
            FileChurn("img.png", "binary", added=None, deleted=None, post_loc=None),
        ]
    )
    rec = ReviewTelemetryRecord(**_row(**result.as_record()))
    assert rec.churn_ratio == 1.0
    assert rec.churn_max_path == "small.py"
    assert rec.churn_excluded_n == 1


def test_empty_measurement_as_record_validates_against_the_row() -> None:
    rec = ReviewTelemetryRecord(**_row(**ChurnMeasurement(None, None, (), ()).as_record()))
    assert rec.churn_measured_n == 0
