"""The three out-of-diff P1s from review round 1, plus the injection they share a shape with.

All four are the same mistake in four places: a value that arrives from OUTSIDE the harness —
a diff line, a filename in that diff, a slug the user typed — is used to build a command, a
path, or a ref, without anything in between. None of them needed a clever fix; each needed
the boundary to exist at all.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker import (
    codex_ledger,
    freeze,
    lens_coverage,
    review_telemetry,
    round_record,
    two_pass_review,
)

# ── the injection: model-authored JSON must never reach a shell ──────────────

_HOSTILE = "it's broken'; touch {marker}; echo '"


def _payload_with(marker: Path) -> dict[str, object]:
    text = _HOSTILE.format(marker=marker)
    return {"pass1": [{"severity": "P1", "summary": text}], "pass2": [{"severity": "P1"}]}


def test_merge_reads_a_file_so_a_hostile_finding_never_reaches_the_shell(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The finding text is reviewer prose ABOUT an attacker-supplied diff.

    Under the old `echo '<json>' | …` the apostrophe in "it's" closed the quoting and the
    rest of the line ran. A path argument carries no content, so there is nothing to escape
    out of — asserted by driving the real entry point with the payload that used to work.
    """
    marker = tmp_path / "PWNED"
    src = tmp_path / "merge.json"
    src.write_text(json.dumps(_payload_with(marker)), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["hm", "merge", "--file", str(src)])
    assert two_pass_review.main() == 0
    assert not marker.exists()
    # And the content survived intact rather than being mangled by quoting.
    out = json.loads(capsys.readouterr().out)
    assert out[0]["severity"] == "P1"


def test_redact_reads_a_file_because_its_input_is_the_diff_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`redact`'s input is more exposed than `merge`'s: it carries the raw diff."""
    src = tmp_path / "ctx.json"
    src.write_text(
        json.dumps({"pr_title": "x", "diff": "- a'; touch /tmp/nope; echo '\n+ b"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["hm", "redact", "--file", str(src)])
    assert two_pass_review.main() == 0
    assert json.loads(capsys.readouterr().out)["pr_title"] == "[REDACTED]"


def test_a_hostile_filename_round_trips_through_the_producer_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repository may contain a file whose NAME is a shell payload.

    `churn_max_path` is a path taken straight out of the measured diff, so the telemetry record
    became attacker-influenced the moment churn measurement shipped. Two properties, unchanged
    in substance by the producer-record rework and both asserted here: no stage of this path
    builds a shell command out of that name, and the name is recorded VERBATIM — a sanitiser
    here would corrupt the very field an operator uses to find the file.

    What did change is where the value enters. `emit` now takes the measured keys only from the
    round record `review_churn measure` wrote, so this exercises the hostile name along the path
    it actually travels; the model cannot put a `churn_max_path` in the row at all.
    """
    hostile = "src/x'; touch /tmp/nope; echo '.py"
    monkeypatch.chdir(tmp_path)
    round_record.merge(
        tmp_path,
        "s",
        1,
        {
            "churn_ratio": 0.5,
            "churn_max_path": hostile,
            "churn_measured_n": 1,
            "churn_excluded_n": 0,
        },
    )
    record = {
        "ts": "2026-08-16T00:00:00Z",
        "slug": "s",
        "round": 1,
        "pass1_n": 0,
        "pass2_kept_n": 0,
        "consensus_passed_n": 0,
        "wall_time_ms": 1,
        "build_break_count": 0,
        "auto_fix_reverted_n": 0,
    }
    src = tmp_path / "row.json"
    src.write_text(json.dumps(record), encoding="utf-8")

    assert review_telemetry.main(["emit", "--file", str(src)]) == 0
    written = Path(capsys.readouterr().out.strip())
    row = json.loads(written.read_text(encoding="utf-8").strip())
    assert row["churn_max_path"] == hostile
    assert not Path("/tmp/nope").exists()


def test_a_transcribed_churn_path_never_reaches_the_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The narrower boundary the rework added: the model is no longer an input here at all.

    Asserted separately from the round-trip above because they fail for different reasons — a
    regression that re-admits the model's value would leave that test green.
    """
    monkeypatch.chdir(tmp_path)
    record = {
        "ts": "2026-08-16T00:00:00Z",
        "slug": "s",
        "round": 1,
        "pass1_n": 0,
        "pass2_kept_n": 0,
        "consensus_passed_n": 0,
        "wall_time_ms": 1,
        "build_break_count": 0,
        "auto_fix_reverted_n": 0,
        "churn_ratio": 0.5,
        "churn_max_path": "src/x'; touch /tmp/nope; echo '.py",
        "churn_measured_n": 1,
        "churn_excluded_n": 0,
    }
    src = tmp_path / "row.json"
    src.write_text(json.dumps(record), encoding="utf-8")

    assert review_telemetry.main(["emit", "--file", str(src)]) == 0
    written = Path(capsys.readouterr().out.strip())
    row = json.loads(written.read_text(encoding="utf-8").strip())
    assert row["churn_max_path"] is None
    assert row["churn_ratio"] is None


def test_the_file_arg_reports_a_missing_path_instead_of_reading_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falling back to stdin on an unreadable path would hang, or silently use stale input."""
    monkeypatch.setattr("sys.argv", ["hm", "merge", "--file", "/nonexistent/x.json"])
    assert two_pass_review.main() == 1


# ── freeze: a slug becomes both a ref and a filesystem path ──────────────────


@pytest.mark.parametrize(
    "slug",
    ["../escape", "a/b", "", "-rf", "x\ny", "..", "with space"],
)
def test_a_traversing_slug_is_refused_by_every_freeze_entry_point(slug: str) -> None:
    """All three, because they fail differently and only one is obvious.

    git rejects `..` in a refname by itself, so the ref builders look safe in isolation —
    but `review_base_stamp` is a plain filesystem join and would write outside the harness
    directory. A leading `-` is the third shape: it turns the ref into an option for the git
    plumbing command that receives it.
    """
    with pytest.raises(ValueError, match="slug must match"):
        freeze.review_base_ref(slug)
    with pytest.raises(ValueError, match="slug must match"):
        freeze.freeze_ref(slug, "confirm-1")
    with pytest.raises(ValueError, match="slug must match"):
        freeze.review_base_stamp(Path("/tmp"), slug)


def test_an_ordinary_slug_still_resolves(tmp_path: Path) -> None:
    """Non-vacuity: the guard must not reject the slugs this repo actually uses."""
    assert freeze.review_base_ref("review-loop-empirics").endswith("review-loop-empirics-base")
    stamp = freeze.review_base_stamp(tmp_path, "review-loop-empirics")
    assert stamp.is_relative_to(tmp_path)


def test_the_freeze_cli_diagnoses_a_bad_slug_instead_of_raising(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every caller is a rendered step that reads this command's stdout as JSON."""
    assert freeze.main(["read-base", "--slug", "../x"]) == 2
    assert "slug must match" in capsys.readouterr().err


# ── codex_ledger: the one-time migration is claimed, not merely checked ──────


def _legacy(base_dir: Path, n: int) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ts": "2026-08-16T00:00:00Z",
            "stage": "review",
            "slug": "s",
            "codex_status": "invoked",
            "disposition": "unresolved",
            "finding_ref": "n/a",
        }
        for _ in range(n)
    ]
    (base_dir / codex_ledger._LEGACY_LEDGER_FILENAME).write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def test_the_legacy_migration_is_claimed_before_it_is_performed(tmp_path: Path) -> None:
    """Two concurrent sessions must not both copy the legacy history forward.

    `/hm:review` and `/hm:plan` in separate sessions over one repo is the NORMAL case for
    this harness, and the file is append-only: a doubled migration permanently doubles every
    rate computed from it, with no way to tell after the fact.
    """
    obs = tmp_path / ".claude" / "observability"
    _legacy(obs, 3)

    codex_ledger._migrate_legacy_ledger(obs)
    first = (obs / codex_ledger.LEDGER_FILENAME).read_text(encoding="utf-8")
    assert len(first.strip().splitlines()) == 3

    # The second caller sees the claim and does nothing — the property the bare
    # `exists()` check also had. The race is asserted below.
    codex_ledger._migrate_legacy_ledger(obs)
    assert (obs / codex_ledger.LEDGER_FILENAME).read_text(encoding="utf-8") == first


def test_the_migration_claim_wins_the_race_not_the_existence_check(tmp_path: Path) -> None:
    """The interleaving the old code lost, run for real in two processes.

    Both processes reach the check before either writes. With `exists()` alone both proceed
    and the file ends with 6 rows; with the O_EXCL claim exactly one proceeds and it has 3.
    """
    obs = tmp_path / ".claude" / "observability"
    _legacy(obs, 3)

    script = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from harness_maker import codex_ledger\n"
        "barrier = Path(sys.argv[2])\n"
        "barrier.write_text('x')\n"
        "while len(list(barrier.parent.glob('barrier-*'))) < 2:\n"
        "    time.sleep(0.01)\n"
        "codex_ledger._migrate_legacy_ledger(Path(sys.argv[1]))\n"
    )
    procs = [
        subprocess.Popen(  # noqa: S603 — fixed argv, shell=False
            [sys.executable, "-c", script, str(obs), str(tmp_path / f"barrier-{i}")],
            cwd=str(Path(__file__).parents[2]),
        )
        for i in range(2)
    ]
    for p in procs:
        p.wait(timeout=60)

    rows = (obs / codex_ledger.LEDGER_FILENAME).read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 3, f"the migration ran twice: {len(rows)} rows"


def test_an_all_malformed_legacy_file_is_not_re_parsed_forever(tmp_path: Path) -> None:
    """The claim stays even when there is nothing to copy — otherwise every emit re-reads it."""
    obs = tmp_path / ".claude" / "observability"
    obs.mkdir(parents=True)
    (obs / codex_ledger._LEGACY_LEDGER_FILENAME).write_text("{not json\n", encoding="utf-8")
    codex_ledger._migrate_legacy_ledger(obs)
    assert (obs / codex_ledger.LEDGER_FILENAME).exists()
    assert (obs / codex_ledger.LEDGER_FILENAME).read_text(encoding="utf-8") == ""


# ── lens_coverage: the run id belongs in the PATH, not only in the file ──────


def _write_result(d: Path, lens: str, run_id: str) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{lens}.json").write_text(
        json.dumps({"lens": lens, "run_id": run_id, "findings": []}), encoding="utf-8"
    )


def test_the_results_path_is_keyed_by_run_id(tmp_path: Path) -> None:
    a = lens_coverage.round_dir(tmp_path, "s", "1", "run-a")
    b = lens_coverage.round_dir(tmp_path, "s", "1", "run-b")
    assert a != b
    assert "run-a" in a.parts


def test_a_previous_invocation_cannot_be_seen_at_all_by_the_next(tmp_path: Path) -> None:
    """Structural isolation, on top of the content check — because the WRITER is a model.

    F2 (measured 2026-08-15): invocation 1 delivers every lens, invocation 2 delivers one,
    and the four dead lenses are vouched for by invocation 1's files. The content `run_id`
    check closes that only while the model stamps the id correctly into each file. Keying the
    directory means invocation 2 never reads invocation 1's directory, whatever is inside it.
    """
    run1 = lens_coverage.round_dir(tmp_path, "s", "1", "run-1")
    for lens in ("design", "functionality", "robustness", "consistency"):
        _write_result(run1, lens, "run-1")

    # Invocation 2: only one lens survives, and it stamps its own id.
    run2 = lens_coverage.round_dir(tmp_path, "s", "1", "run-2")
    _write_result(run2, "design", "run-2")

    verdict = lens_coverage.coverage_verdict([run2], "run-2", "Side")
    assert verdict["exercised"] == ["design"]
    assert verdict["blocks_approval"] is True


def test_a_mis_stamped_file_in_the_right_directory_is_still_rejected(tmp_path: Path) -> None:
    """Both checks stay. The path keying does not license dropping the content one."""
    d = lens_coverage.round_dir(tmp_path, "s", "1", "run-2")
    _write_result(d, "design", "run-1")  # right directory, wrong id inside
    assert lens_coverage.exercised_lenses(d, "run-2") == set()


def test_a_traversing_run_id_is_contained(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        lens_coverage.round_dir(tmp_path, "s", "1", "../../etc")
