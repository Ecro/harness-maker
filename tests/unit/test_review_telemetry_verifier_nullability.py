"""ADR-002 of PLAN-workflow-loop-efficiency — the verifier counts became nullable.

`0` would read as "the verifier ran and dropped nothing". These rows are append-only, so
a wrong value is permanent and un-fixable after the fact — the same row-kind conflation
already shipped once in `second-opinion.jsonl`, where `finding_ref` had to become the
discriminator retroactively because `status: "invoked"` meant two different things.

The distinction this file protects is three-way and every arm is asserted below:
  * absent   → the Pass 1.5 dispatch did not exist (post-ADR-001 rows)
  * integer  → the verifier ran and reported that count (pre-ADR-001 rows, still parse)
  * partial  → one set and one absent is incoherent and must not be writable
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from harness_maker.review_telemetry import ReviewTelemetryRecord, emit, record_from_dict

_BASE: dict[str, Any] = {
    "ts": "2026-08-05T00:00:00Z",
    "slug": "workflow-loop-efficiency",
    "round": 1,
    "pass1_n": 7,
    "pass2_kept_n": 5,
    "consensus_passed_n": 3,
    "wall_time_ms": 1234,
    "build_break_count": 0,
    "auto_fix_reverted_n": 0,
}


def test_a_post_removal_row_omits_both_counts() -> None:
    rec = record_from_dict(dict(_BASE))
    assert rec.verifier_kept_n is None
    assert rec.verifier_dropped_n is None


def test_a_pre_removal_row_still_parses() -> None:
    """Backward compatibility is the whole reason this is `| None` and not a deletion.

    Dropping the fields would make every archived row fail `extra="forbid"`, destroying
    the historical series the ablation measurement (P5) reads.
    """
    rec = record_from_dict({**_BASE, "verifier_kept_n": 6, "verifier_dropped_n": 1})
    assert (rec.verifier_kept_n, rec.verifier_dropped_n) == (6, 1)


def test_null_is_distinguishable_from_zero_after_a_round_trip() -> None:
    """The distinction has to survive serialization, not just live in the model.

    A row that serialized `None` to `0` would be indistinguishable on disk from a real
    run that dropped nothing — and disk is the only copy.
    """
    absent = json.loads(record_from_dict(dict(_BASE)).model_dump_json())
    measured_zero = json.loads(
        record_from_dict({**_BASE, "verifier_kept_n": 0, "verifier_dropped_n": 0}).model_dump_json()
    )
    assert absent["verifier_kept_n"] is None
    assert measured_zero["verifier_kept_n"] == 0
    assert absent != measured_zero


@pytest.mark.parametrize(
    "partial",
    [
        {"verifier_kept_n": 6},
        {"verifier_dropped_n": 1},
    ],
)
def test_a_half_filled_pair_is_rejected(partial: dict[str, int]) -> None:
    """Both-or-neither. One set and one absent has no coherent reading.

    Without this the nullability is a strictly weaker schema than the integers it
    replaced: it would newly admit a shape that was previously impossible to write.
    """
    with pytest.raises(ValidationError):
        record_from_dict({**_BASE, **partial})


def test_the_counts_are_still_bounded_below() -> None:
    """`| None` must not have relaxed `ge=0` on the integer arm."""
    with pytest.raises(ValidationError):
        record_from_dict({**_BASE, "verifier_kept_n": -1, "verifier_dropped_n": 0})


def test_the_emitted_line_carries_the_nulls(tmp_path: Path) -> None:
    """End-to-end through the real append path, not just the model."""
    path = emit(ReviewTelemetryRecord(**_BASE), project_root=tmp_path)
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["verifier_kept_n"] is None
    assert row["verifier_dropped_n"] is None
