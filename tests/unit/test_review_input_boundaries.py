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
