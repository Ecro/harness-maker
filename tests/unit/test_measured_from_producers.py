"""The measured fields come from the producers' own output, never from the model.

Measured on this repository's ledger before this change, 69 rows: `churn_ratio` 0/69,
`churn_measured_n` 0/69, `lenses_exercised` 0/69, `confirm_pass_ran` 0/69 — while all nine
REQUIRED fields were present in every row. A schema optional is a prompt optional, and the prose
saying "always, per round" did not survive it. `review_churn.DEFAULT_CHURN_RATIO` records what
that cost: a live gate threshold set from an estimate because the recalibration data never
arrived across four repositories and 123 rows.

The arm that matters most is `test_a_row_that_omits_everything_still_gets_the_numbers`: it
reproduces the exact 0/69 behaviour — a model row carrying none of the measured keys — and
asserts the numbers land anyway.

**This suite replaced one written against a shared scratch store.** That store had to answer
three questions a file path does not — which root it lives under, how two writers coordinate,
how two runs stay apart — and those three answers produced five P1 findings across two review
rounds, none of them in the feature. The tests that went with it are gone too; what a store
needed proving about locks and run identity has no subject any more.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker import review_churn, review_consensus, review_telemetry
from harness_maker.review_telemetry import MEASURED_KEYS, ReviewTelemetryRecord

_LENS = {"source": "design", "kind": "lens"}


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ts": "2026-08-20T00:00:00Z",
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


def _write(name: str, payload: dict[str, Any]) -> str:
    Path(name).write_text(json.dumps(payload), encoding="utf-8")
    return name


def _emitted(tmp_path: Path) -> dict[str, Any]:
    written = list((tmp_path / ".claude" / "observability").glob("review-*.jsonl"))
    assert len(written) == 1, f"expected one ledger file, got {written}"
    return json.loads(written[0].read_text(encoding="utf-8").strip())


@pytest.fixture
def at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ── the producers stamp their own output ─────────────────────────────────────


def test_finalize_stamps_slug_and_round_onto_its_payload(at: Path, capsys: Any) -> None:
    findings = [
        {"id": "a", "severity": "P1", "disposition": "accepted", "voices": [_LENS]},
        {"id": "b", "severity": "P2", "disposition": "duplicate", "voices": [_LENS]},
    ]
    Path("f.json").write_text(json.dumps(findings), encoding="utf-8")
    assert (
        review_consensus.main(["finalize", "--file", "f.json", "--slug", "d", "--round", "3"]) == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["slug"] == "d"
    assert payload["round"] == 3
    assert payload["disposition_counts"] == {
        "accepted": 1,
        "duplicate": 1,
        "rejected": 0,
        "unresolved": 0,
    }


def test_finalize_without_the_flags_stamps_nothing(at: Path, capsys: Any) -> None:
    """Optional on purpose — every pre-existing caller keeps working unchanged."""
    Path("f.json").write_text(json.dumps([]), encoding="utf-8")
    assert review_consensus.main(["finalize", "--file", "f.json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "slug" not in payload
    assert "round" not in payload


def test_the_churn_payload_carries_exactly_the_record_keys() -> None:
    """`as_record` feeds the row; it must not drift from what `emit` will pick up."""
    measurement = review_churn.ChurnMeasurement(
        ratio=0.5, max_path="a.py", measured=(("a.py", 0.5),), excluded=()
    )
    assert set(measurement.as_record()) <= set(MEASURED_KEYS)


# ── emit takes them from those files and from nowhere else ───────────────────


def test_a_row_that_omits_everything_still_gets_the_numbers(at: Path) -> None:
    """The 0/69 case, reproduced: the model sends none of the measured keys."""
    producer = _write(
        "finalize.json",
        {
            "slug": "demo",
            "round": 1,
            "grade": "A",
            "findings": [],
            "disposition_counts": {"accepted": 3},
        },
    )
    churn = _write(
        "churn.json",
        {
            "slug": "demo",
            "round": 1,
            "churn_ratio": 0.5,
            "churn_max_path": "a.py",
            "churn_measured_n": 1,
            "churn_excluded_n": 0,
            "measured": [{"path": "a.py", "ratio": 0.5}],
        },
    )
    args = ["emit", "--file", _write("row.json", _row()), "--measured", producer]
    assert review_telemetry.main([*args, "--measured", churn]) == 0
    written = _emitted(at)
    assert written["disposition_counts"] == {"accepted": 3}
    assert written["churn_ratio"] == 0.5
    assert written["churn_measured_n"] == 1


def test_only_the_measured_keys_are_taken_from_a_producer_payload(at: Path) -> None:
    """`findings` and `grade` are in that file too; an append-only row must not absorb them."""
    producer = _write(
        "finalize.json",
        {
            "slug": "demo",
            "round": 1,
            "grade": "D",
            "findings": [{"id": "x"}],
            "counts": {"P0": 1},
            "disposition_counts": {"accepted": 1},
        },
    )
    assert (
        review_telemetry.main(
            ["emit", "--file", _write("row.json", _row()), "--measured", producer]
        )
        == 0
    )
    written = _emitted(at)
    assert written["disposition_counts"] == {"accepted": 1}
    for leaked in ("grade", "findings", "counts"):
        assert leaked not in written


def test_a_transcribed_value_is_discarded_and_reported(at: Path, capsys: Any) -> None:
    """Stripping, not defaulting.

    Accepting the model's value when it disagrees is how a wrong transcription becomes a
    permanent row; accepting it when NO producer file was passed is how the field goes back to
    being optional, which is the whole defect.
    """
    producer = _write(
        "finalize.json", {"slug": "demo", "round": 1, "disposition_counts": {"accepted": 3}}
    )
    row = _row(
        disposition_counts={"accepted": 99},
        churn_ratio=0.9,
        churn_max_path="b.py",
        churn_measured_n=7,
        churn_excluded_n=0,
    )
    assert (
        review_telemetry.main(["emit", "--file", _write("row.json", row), "--measured", producer])
        == 0
    )
    written = _emitted(at)
    assert written["disposition_counts"] == {"accepted": 3}
    assert written["churn_ratio"] is None, "a value with no producer behind it must not survive"
    err = capsys.readouterr().err
    assert "discarded transcribed value" in err


def test_an_absent_producer_does_not_let_the_model_supply_the_numbers(at: Path) -> None:
    """The wrong implementation this suite exists to distinguish:

    if measured: out.update(measured)
    else:        out.update(supplied)   # <- restores the field to optional
    """
    row = _row(disposition_counts={"accepted": 99})
    assert review_telemetry.main(["emit", "--file", _write("row.json", row)]) == 0
    assert _emitted(at)["disposition_counts"] is None


def test_no_producer_output_is_loud(at: Path, capsys: Any) -> None:
    """Null measures are honest; silence about them is not."""
    assert review_telemetry.main(["emit", "--file", _write("row.json", _row())]) == 0
    assert _emitted(at)["disposition_counts"] is None
    err = capsys.readouterr().err
    assert "no producer output" in err
    assert "--measured" in err


# ── the one hazard passing paths introduces, closed deterministically ────────


def test_a_producer_file_from_another_round_is_refused(at: Path, capsys: Any) -> None:
    """A stale path is the failure mode a shared store did not have. It is decidable, so decide it.

    Silently merging round 2's numbers into round 3's row would be the same wrong-number outcome
    the whole change exists to prevent, arriving by a different door.
    """
    stale = _write(
        "finalize-r2.json", {"slug": "demo", "round": 2, "disposition_counts": {"accepted": 9}}
    )
    row = _row(round=3)
    assert (
        review_telemetry.main(["emit", "--file", _write("row.json", row), "--measured", stale]) == 0
    )
    assert _emitted(at)["disposition_counts"] is None
    assert "does not match the row" in capsys.readouterr().err


def test_a_producer_file_from_another_slug_is_refused(at: Path, capsys: Any) -> None:
    other = _write(
        "finalize.json", {"slug": "other", "round": 1, "disposition_counts": {"accepted": 9}}
    )
    assert (
        review_telemetry.main(["emit", "--file", _write("row.json", _row()), "--measured", other])
        == 0
    )
    assert _emitted(at)["disposition_counts"] is None
    assert "does not match the row" in capsys.readouterr().err


def test_an_unstamped_producer_file_is_accepted(at: Path) -> None:
    """A payload from before the stamp carries neither key; refusing it would be a regression."""
    legacy = _write("finalize.json", {"disposition_counts": {"accepted": 2}})
    assert (
        review_telemetry.main(["emit", "--file", _write("row.json", _row()), "--measured", legacy])
        == 0
    )
    assert _emitted(at)["disposition_counts"] == {"accepted": 2}


def test_an_unreadable_producer_file_is_reported_not_fatal(at: Path, capsys: Any) -> None:
    """A review must never fail over telemetry."""
    Path("broken.json").write_text("{not json", encoding="utf-8")
    args = ["emit", "--file", _write("row.json", _row()), "--measured", "broken.json"]
    assert review_telemetry.main([*args, "--measured", "/nonexistent.json"]) == 0
    assert _emitted(at)["disposition_counts"] is None
    err = capsys.readouterr().err
    assert "unreadable producer output" in err


def test_missing_path_after_the_flag_is_a_usage_error(at: Path) -> None:
    assert review_telemetry.main(["emit", "--file", "row.json", "--measured"]) == 2


# ── schema arms that outlive the store ───────────────────────────────────────


def test_null_and_empty_are_different_facts() -> None:
    """Null = this version never measured. `{}` = measured, and the round had no findings."""
    assert ReviewTelemetryRecord(**_row()).disposition_counts is None
    assert ReviewTelemetryRecord(**_row(disposition_counts={})).disposition_counts == {}


def test_an_off_vocabulary_disposition_is_rejected() -> None:
    """These four literally reached disk once; nothing rejected them then."""
    for shipped_by_accident in ("fixed", "accepted-not-fixed", "deferred", "out-of-scope"):
        with pytest.raises(ValueError, match=shipped_by_accident):
            ReviewTelemetryRecord(**_row(disposition_counts={shipped_by_accident: 1}))
