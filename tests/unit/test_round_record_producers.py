"""The measured fields come from the producer, never from the model's transcription.

Measured on this repository's own ledger before this change, 69 rows: `churn_ratio` 0/69,
`churn_measured_n` 0/69, `lenses_exercised` 0/69, `confirm_pass_ran` 0/69 — while all nine
REQUIRED fields were present in every row. A schema optional is a prompt optional, and the
prose saying "always, per round" did not survive it. `review_churn.DEFAULT_CHURN_RATIO`
records what that cost: a live gate threshold set from an estimate because the recalibration
data never arrived across four repositories and 123 rows.

The arm that matters most here is `test_a_row_that_omits_everything_still_gets_the_numbers`:
it reproduces the exact 0/69 behaviour — a model row with none of the measured keys — and
asserts the numbers land anyway.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker import review_churn, review_consensus, review_telemetry, round_record

_LENS = {"source": "design", "kind": "lens"}


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ts": "2026-08-19T00:00:00Z",
        "slug": "demo",
        "round": 1,
        "pass1_n": 2,
        "pass2_kept_n": 2,
        "consensus_passed_n": 2,
        "wall_time_ms": 10,
        "build_break_count": 0,
        "auto_fix_reverted_n": 0,
    }
    base.update(overrides)
    return base


def _emitted(tmp_path: Path) -> dict[str, Any]:
    written = list((tmp_path / ".claude" / "observability").glob("review-*.jsonl"))
    assert len(written) == 1, f"expected one ledger file, got {written}"
    return json.loads(written[0].read_text(encoding="utf-8").strip())


@pytest.fixture
def at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`emit` resolves the round record from cwd, as it does in a real stage."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_finalize_records_its_own_counts(at: Path) -> None:
    findings = [
        {"id": "a", "severity": "P1", "disposition": "accepted", "voices": [_LENS]},
        {"id": "b", "severity": "P2", "disposition": "duplicate", "voices": [_LENS]},
    ]
    Path("f.json").write_text(json.dumps(findings), encoding="utf-8")
    assert (
        review_consensus.main(["finalize", "--file", "f.json", "--slug", "d", "--round", "1"]) == 0
    )
    assert round_record.read(at, "d", 1) == {
        "disposition_counts": {"accepted": 1, "duplicate": 1, "rejected": 0, "unresolved": 0}
    }


def test_finalize_without_the_flags_records_nothing(at: Path) -> None:
    """Optional on purpose — every pre-existing caller keeps working unchanged."""
    Path("f.json").write_text(json.dumps([]), encoding="utf-8")
    assert review_consensus.main(["finalize", "--file", "f.json"]) == 0
    assert round_record.read(at, "d", 1) == {}


def test_a_row_that_omits_everything_still_gets_the_numbers(at: Path) -> None:
    """The 0/69 case, reproduced: the model sends none of the measured keys."""
    # A coherent churn set: the record schema forbids a ratio with no counts behind it, and
    # the producer always writes all four together (`ChurnMeasurement.as_record`).
    round_record.merge(
        at,
        "demo",
        1,
        {
            "disposition_counts": {"accepted": 3},
            "churn_ratio": 0.5,
            "churn_max_path": "a.py",
            "churn_measured_n": 1,
            "churn_excluded_n": 0,
        },
    )
    assert review_telemetry.main(["emit", "--file", _write_row(_row())]) == 0
    written = _emitted(at)
    assert written["disposition_counts"] == {"accepted": 3}
    assert written["churn_ratio"] == 0.5
    assert written["churn_measured_n"] == 1


def test_a_transcribed_value_is_discarded_and_reported(
    at: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Stripping, not defaulting.

    Accepting the model's value when it disagrees is how a wrong transcription becomes a
    permanent row; accepting it when the record is EMPTY is how the field goes back to being
    optional, which is the whole defect.
    """
    round_record.merge(at, "demo", 1, {"disposition_counts": {"accepted": 3}})
    row = _row(
        disposition_counts={"accepted": 99},
        churn_ratio=0.9,
        churn_max_path="b.py",
        churn_measured_n=7,
        churn_excluded_n=0,
    )
    assert review_telemetry.main(["emit", "--file", _write_row(row)]) == 0
    written = _emitted(at)
    assert written["disposition_counts"] == {"accepted": 3}
    assert written["churn_ratio"] is None, "a value with no producer behind it must not survive"
    err = capsys.readouterr().err
    assert "discarded transcribed value" in err
    assert "churn_ratio" in err
    assert "disposition_counts" in err


def test_no_producer_record_is_loud(at: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Null measures are honest; silence about them is not."""
    assert review_telemetry.main(["emit", "--file", _write_row(_row())]) == 0
    assert _emitted(at)["disposition_counts"] is None
    err = capsys.readouterr().err
    assert "no producer record" in err
    assert "review_consensus finalize" in err


def test_two_producers_merge_rather_than_overwrite(at: Path) -> None:
    """`finalize` writes first and `review_churn measure` second, into one file."""
    round_record.merge(at, "demo", 2, {"disposition_counts": {"accepted": 1}})
    round_record.merge(at, "demo", 2, {"churn_ratio": 0.25, "churn_measured_n": 3})
    assert round_record.read(at, "demo", 2) == {
        "disposition_counts": {"accepted": 1},
        "churn_ratio": 0.25,
        "churn_measured_n": 3,
    }


def test_the_churn_measurement_shape_is_exactly_the_record_keys() -> None:
    """`as_record` and `MEASURED_KEYS` must not drift — one feeds the other verbatim."""
    measurement = review_churn.ChurnMeasurement(
        ratio=0.5, max_path="a.py", measured=(("a.py", 0.5),), excluded=()
    )
    assert set(measurement.as_record()) <= set(round_record.MEASURED_KEYS)


def test_a_slug_cannot_escape_the_store(at: Path) -> None:
    """Every path component here is model-substituted out of rendered prose."""
    path = round_record.record_path(at, "../../../../etc/evil", 1)
    store = (at / ".claude" / "observability" / round_record.ROUND_DIRNAME).resolve()
    assert path.resolve().parent == store


def test_a_malformed_record_reads_as_empty_rather_than_raising(at: Path) -> None:
    """A scratch file must never be able to fail a review."""
    path = round_record.record_path(at, "demo", 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert round_record.read(at, "demo", 1) == {}


def _write_row(row: dict[str, Any]) -> str:
    Path("row.json").write_text(json.dumps(row), encoding="utf-8")
    return "row.json"
