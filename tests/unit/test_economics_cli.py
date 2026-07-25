"""Phase 3 contract: CLI output shape against the fixture store + config round-trip.

Every gate here is CI-runnable: the numbers are pinned against the checked-in fixture
transcripts, and `--now` freezes the window so the suite does not rot with the clock.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.economics import main
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import EconomicsConfig, InterviewAnswers

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "transcripts"
_PROJECT = "/repo/proj"
_NOW = "2026-07-25T14:00:00+00:00"


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, object]]:
    code = main(list(argv))
    return code, json.loads(capsys.readouterr().out)


# ---------------------------------------------------------------- report


def test_report_prices_the_fixture_store(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run(
        capsys,
        "report",
        "--root",
        _PROJECT,
        "--transcript-root",
        str(_FIXTURES),
        "--now",
        _NOW,
    )
    assert code == 0
    assert payload["status"] == "ok"
    report = payload["report"]
    assert isinstance(report, dict)
    assert report["turns"] == 7
    assert report["total_usd"] > 0
    assert set(report["by_stage"]) == {"hm:execute", "hm:review", "hm:plan", "(unattributed)"}
    assert report["price_table_version"]


def test_report_carries_ingestion_diagnostics(capsys: pytest.CaptureFixture[str]) -> None:
    _code, payload = _run(
        capsys, "report", "--root", _PROJECT, "--transcript-root", str(_FIXTURES), "--now", _NOW
    )
    ingestion = payload["ingestion"]
    assert isinstance(ingestion, dict)
    assert ingestion["dirs_scanned"] == 2
    assert ingestion["files_discovered"] == 3
    assert ingestion["files_failed"] == 0
    assert ingestion["turns_with_usage"] == 7
    assert ingestion["coverage"] == pytest.approx(7 / 8)


def test_report_annotates_that_external_model_cost_is_unmeasured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR-008 — the incompleteness must be visible, not implied."""
    _code, payload = _run(
        capsys, "report", "--root", _PROJECT, "--transcript-root", str(_FIXTURES), "--now", _NOW
    )
    assert payload["external_models_unmeasured"] is True


def test_report_json_contains_no_cost_per_count_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR-002 at the wire boundary, not just in the Python schema."""
    _code, payload = _run(
        capsys, "report", "--root", _PROJECT, "--transcript-root", str(_FIXTURES), "--now", _NOW
    )
    blob = json.dumps(payload)
    for forbidden in ("cost_per", "usd_per", "_per_commit", "per_finding", "per_deliverable"):
        assert forbidden not in blob


def test_window_excludes_turns_older_than_the_configured_days(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _code, payload = _run(
        capsys,
        "report",
        "--root",
        _PROJECT,
        "--transcript-root",
        str(_FIXTURES),
        "--days",
        "1",
        "--now",
        "2027-01-01T00:00:00+00:00",
    )
    report = payload["report"]
    assert isinstance(report, dict)
    assert report["turns"] == 0


# ---------------------------------------------------------------- stages


def test_stages_lists_stages_newest_spend_first(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run(
        capsys, "stages", "--root", _PROJECT, "--transcript-root", str(_FIXTURES), "--now", _NOW
    )
    assert code == 0
    stages = payload["stages"]
    assert isinstance(stages, list)
    totals = [row["total_usd"] for row in stages]
    assert totals == sorted(totals, reverse=True)
    assert {row["stage"] for row in stages} == {
        "hm:execute",
        "hm:review",
        "hm:plan",
        "(unattributed)",
    }


# ---------------------------------------------------------------- doctor


def test_doctor_is_ok_when_the_reader_prices_turns(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run(capsys, "doctor", "--root", _PROJECT, "--transcript-root", str(_FIXTURES))
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["turns_priced"] == 7


def test_doctor_is_na_when_no_transcript_store_exists(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Fresh clone, CI, Cursor and Codex must degrade to N/A — never FAIL."""
    code, payload = _run(capsys, "doctor", "--root", _PROJECT, "--transcript-root", str(tmp_path))
    assert code == 0
    assert payload["status"] == "n/a"


def test_doctor_fails_when_sessions_exist_but_nothing_prices(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The silent-degradation backstop: files present, zero priced turns."""
    store = tmp_path / "-repo-proj"
    store.mkdir(parents=True)
    (store / "sess.jsonl").write_text(
        '{"type":"assistant","sessionId":"x","timestamp":"2026-07-25T12:00:00.000Z",'
        '"message":{"model":"claude-opus-5","content":[]}}\n',
        encoding="utf-8",
    )
    code, payload = _run(capsys, "doctor", "--root", _PROJECT, "--transcript-root", str(tmp_path))
    assert code == 1
    assert payload["status"] == "fail"


# ---------------------------------------------------------------- config round-trip


def test_economics_block_round_trips_through_harness_yaml(tmp_path: Path) -> None:
    """Checkpoint 6 — what synthesize writes, answers_from_harness_yaml must read back."""
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text(
        "preset: Production\n"
        "locale: en\n"
        "economics:\n"
        "  window_days: 7\n"
        '  price_model: "sonnet"\n'
        "  adjacency_estimate: false\n"
        "  adjacency_max_gap_min: 3.5\n"
        "  adjacency_max_turns: 4\n"
        "  idle_gap_cap_min: 2.0\n",
        encoding="utf-8",
    )
    answers = answers_from_harness_yaml(claude / "harness.yaml")
    assert answers is not None
    assert answers.economics.window_days == 7
    assert answers.economics.price_model == "sonnet"
    assert answers.economics.adjacency_estimate is False
    assert answers.economics.adjacency_max_gap_min == pytest.approx(3.5)
    assert answers.economics.adjacency_max_turns == 4
    assert answers.economics.idle_gap_cap_min == pytest.approx(2.0)


def test_absent_economics_block_falls_back_to_defaults(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text("preset: Production\nlocale: en\n", encoding="utf-8")
    answers = answers_from_harness_yaml(claude / "harness.yaml")
    assert answers is not None
    assert answers.economics == EconomicsConfig()


def test_malformed_economics_block_falls_back_to_defaults(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text(
        'preset: Production\nlocale: en\neconomics:\n  window_days: "not a number"\n',
        encoding="utf-8",
    )
    answers = answers_from_harness_yaml(claude / "harness.yaml")
    assert answers is not None
    assert answers.economics == EconomicsConfig()


def test_interview_answers_accepts_the_economics_key() -> None:
    """extra='forbid' would reject the round-trip without the mirror declaration."""
    answers = InterviewAnswers(economics=EconomicsConfig(window_days=3))
    assert answers.economics.window_days == 3
