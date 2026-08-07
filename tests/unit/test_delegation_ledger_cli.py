"""`hm delegation_ledger record` driven as a real subprocess, in its shipped spelling.

Added because `tests/structural/test_cli_surfaces_are_driven.py` found it — of the 30
shipped `hm` subcommands, this was the ONE with no test invoking it as the user does. That
is `[fail:test] shipped-entry-point-not-exercised` (count:4) waiting to happen: the module's
functions may be covered, but the argparse wiring, the subcommand name, and the base-root
resolution are only exercised by a real invocation.

It also matters more than most: the wrapup stage calls this on its self-skip branch, and the
whole point of that row is to keep "no dispatch tool in this IDE" distinguishable from
"dispatch never fired". A silently-broken recorder makes those two identical again.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "."], cwd=repo, check=True, capture_output=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    return repo


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.delegation_ledger", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _rows(repo: Path) -> list[dict[str, object]]:
    hits = list((repo / ".claude" / "observability").glob("*delegation*.jsonl"))
    assert hits, "no delegation ledger file was written"
    return [json.loads(line) for line in hits[0].read_text(encoding="utf-8").splitlines() if line]


def test_record_writes_a_row_with_the_fields_it_was_given(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    cp = _run(
        repo,
        "record",
        "--root",
        ".",
        "--stage",
        "wrapup",
        "--slug",
        "demo",
        "--kind",
        "dispatch",
        "--status",
        "unavailable",
        "--reason",
        "no dispatch tool",
    )
    assert cp.returncode == 0, cp.stderr
    rows = _rows(repo)
    assert len(rows) == 1
    row = rows[0]
    assert row["stage"] == "wrapup"
    assert row["slug"] == "demo"
    assert row["kind"] == "dispatch"
    assert row["status"] == "unavailable"
    assert row["reason"] == "no dispatch tool"


def test_rows_append_rather_than_replace(tmp_path: Path) -> None:
    """A ledger that overwrites is worse than none — it reports the last call as the only one."""
    repo = _repo(tmp_path)
    # Both statuses must be valid for --kind dispatch: the CLI enforces a kind/status
    # pairing (`ok` belongs to --kind brief), which driving the shipped surface revealed.
    for status in ("dispatched", "mismatch"):
        cp = _run(
            repo,
            "record",
            "--root",
            ".",
            "--stage",
            "wrapup",
            "--slug",
            "demo",
            "--kind",
            "dispatch",
            "--status",
            status,
        )
        assert cp.returncode == 0, cp.stderr
    assert [r["status"] for r in _rows(repo)] == ["dispatched", "mismatch"]


@pytest.mark.parametrize("bad", ["not-a-status", "DISPATCHED", "", "ok"])
def test_an_unknown_status_is_rejected(tmp_path: Path, bad: str) -> None:
    """The enum is the ledger's only guarantee that a later aggregation can trust the column.

    `"ok"` is in the parametrize on purpose: it is a REAL status of this CLI, but only for
    `--kind brief`. A pairing the argparse choices alone would accept is exactly the kind of
    contract a unit test on the module's functions never sees.
    """
    repo = _repo(tmp_path)
    cp = _run(
        repo,
        "record",
        "--root",
        ".",
        "--stage",
        "wrapup",
        "--slug",
        "demo",
        "--kind",
        "dispatch",
        "--status",
        bad,
    )
    assert cp.returncode != 0, f"status {bad!r} was accepted"
