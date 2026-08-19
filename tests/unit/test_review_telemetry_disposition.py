"""REV-1 — Step 4e's dispositions reach disk, and an off-vocabulary one does not.

The gate ADR-002 shipped had no measurement surface: `finalize` writes nothing, and the
ledger's per-finding disposition rows are a closed enum of second-opinion vendors, so a
reviewer-lens disposition had no value that would name it. The rejection rate — the number
that decides whether the gate works at all — was unanswerable from disk.

Every `pytest.raises` here excludes `extra_forbidden`, or the assertions pass against a
schema that ships no such field at all, which is the RED gate reading green.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from harness_maker import review_consensus, review_telemetry
from harness_maker.codex_ledger import DISPOSITION_VALUES
from harness_maker.review_telemetry import ReviewTelemetryRecord, emit

_LENS = {"source": "design", "kind": "lens"}


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ts": "2026-08-19T00:00:00Z",
        "slug": "review-loop-ledger",
        "round": 1,
        "pass1_n": 4,
        "pass2_kept_n": 4,
        "consensus_passed_n": 3,
        "wall_time_ms": 1000,
        "build_break_count": 0,
        "auto_fix_reverted_n": 0,
    }
    base.update(overrides)
    return base


def _rejected_by_a_rule(**row: Any) -> list[Any]:
    with pytest.raises(ValidationError) as excinfo:
        ReviewTelemetryRecord(**row)
    errors = [e for e in excinfo.value.errors() if e["type"] != "extra_forbidden"]
    assert errors, "rejected only by the extra-key guard — the rule does not exist"
    return errors


def test_the_four_dispositions_are_accepted() -> None:
    counts = dict.fromkeys(sorted(DISPOSITION_VALUES), 1)
    record = ReviewTelemetryRecord(**_row(disposition_counts=counts))
    assert record.disposition_counts == counts


def test_null_and_empty_are_different_facts() -> None:
    """Null = this version never measured. `{}` = measured, and the round had no findings.

    Collapsing them would make a legacy row and a genuinely finding-free round
    indistinguishable in an append-only ledger — the same failure the churn counts
    and `lenses_exercised` are shaped to avoid.
    """
    assert ReviewTelemetryRecord(**_row()).disposition_counts is None
    assert ReviewTelemetryRecord(**_row(disposition_counts={})).disposition_counts == {}


def test_an_off_vocabulary_disposition_is_rejected() -> None:
    """These four literally reached disk once; nothing rejected them then."""
    for shipped_by_accident in ("fixed", "accepted-not-fixed", "deferred", "out-of-scope"):
        errors = _rejected_by_a_rule(**_row(disposition_counts={shipped_by_accident: 1}))
        assert any(shipped_by_accident in str(e["msg"]) for e in errors)


def test_a_negative_count_is_rejected() -> None:
    errors = _rejected_by_a_rule(**_row(disposition_counts={"accepted": -1}))
    assert any("negative" in str(e["msg"]) for e in errors)


def test_the_vocabulary_is_not_restated_here_or_in_the_model() -> None:
    """One source for the enum. A second list is how the two drift apart."""
    assert {"accepted", "rejected", "duplicate", "unresolved"} == DISPOSITION_VALUES
    source = Path(review_telemetry.__file__).read_text(encoding="utf-8")
    assert "DISPOSITION_VALUES" in source
    assert '"duplicate"' not in source, "the enum is restated instead of imported"


def test_the_counts_survive_the_round_trip_to_disk(tmp_path: Path) -> None:
    counts = {"accepted": 12, "rejected": 3, "duplicate": 1, "unresolved": 2}
    emit(ReviewTelemetryRecord(**_row(disposition_counts=counts)), project_root=tmp_path)
    written = list((tmp_path / ".claude" / "observability").glob("review-*.jsonl"))
    assert len(written) == 1
    row = json.loads(written[0].read_text(encoding="utf-8").strip())
    assert row["disposition_counts"] == counts


def test_an_unmeasured_row_stays_null_on_disk(tmp_path: Path) -> None:
    """A reader computing a rejection rate must be able to exclude pre-change rows."""
    emit(ReviewTelemetryRecord(**_row()), project_root=tmp_path)
    written = list((tmp_path / ".claude" / "observability").glob("review-*.jsonl"))
    row = json.loads(written[0].read_text(encoding="utf-8").strip())
    assert row["disposition_counts"] is None


def test_finalize_supplies_the_counts_so_no_caller_tallies_them() -> None:
    """The template tells the model to copy this field, not to count findings by hand."""
    out = review_consensus.finalize(
        [
            {"id": "a", "severity": "P1", "disposition": "accepted", "voices": [_LENS]},
            {"id": "b", "severity": "P2", "disposition": "duplicate", "voices": [_LENS]},
        ]
    )
    assert out["disposition_counts"] == {
        "accepted": 1,
        "duplicate": 1,
        "rejected": 0,
        "unresolved": 0,
    }
    # `counts` is SEVERITY. A caller reaching for "the counts" must not get P0..P3 here.
    assert set(out["counts"]) == {"P0", "P1", "P2", "P3"}
    ReviewTelemetryRecord(**_row(disposition_counts=out["disposition_counts"]))


def test_the_counts_are_taken_after_ac_verification_not_before() -> None:
    """A `rejected` no machine SPEC can verify is `unresolved` by the time the grade is set.

    Counting the proposed value instead would report a rejection the gate did not honour —
    and on a SPEC-less harness that is EVERY rejection, so the rate would read 100% wrong in
    exactly the population where it reads ~0 for real.
    """
    out = review_consensus.finalize(
        [
            {
                "id": "b",
                "severity": "P2",
                "disposition": "rejected",
                "authority": "AC-004",
                "voices": [_LENS],
            }
        ]
    )
    assert out["disposition_counts"] == {
        "accepted": 0,
        "duplicate": 0,
        "rejected": 0,
        "unresolved": 1,
    }
