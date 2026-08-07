"""`hm mutation_receipt record` — driven as a subprocess, in its shipped spelling.

Written because `tests/structural/test_cli_surfaces_are_driven.py` demanded it the moment
the subcommand was registered. That is the guard working: a new entry point cannot ship
without something running it ([fail:test] shipped-entry-point-not-exercised, count:4).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker import mutation_receipt

_LEDGER = ".claude/observability/mutation-receipts.jsonl"
_GATE = "tests/structural/test_no_dead_string_pins.py::test_no_test_pins_a_leading_step_number"
_DELETES = "tests/structural/test_no_dead_string_pins.py:35"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    return repo


def _rows(repo: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (repo / _LEDGER).read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_the_shipped_entry_point_records_a_row(tmp_path: Path) -> None:
    """The subprocess form — the one a stage actually runs."""
    repo = _repo(tmp_path)
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.mutation_receipt",
            "record",
            "--root",
            str(repo),
            "--gate",
            _GATE,
            "--deletes",
            _DELETES,
            "--slug",
            "demo",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert cp.returncode == 0, cp.stderr
    rows = _rows(repo)
    assert len(rows) == 1
    assert rows[0]["gate"] == _GATE
    assert rows[0]["deletes"] == _DELETES
    assert rows[0]["slug"] == "demo"


def test_rows_append(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    for _ in range(2):
        mutation_receipt.record(repo, gate=_GATE, deletes=_DELETES)
    assert len(_rows(repo)) == 2


# --- the point of the whole thing: a non-answer is rejected ----------------------------


@pytest.mark.parametrize(
    "deletes",
    [
        "worktree.py",  # no line — "somewhere in that module"
        "somewhere in the gate",  # prose
        "src/harness_maker/x.py:abc",  # not a line number
        "",
        # Privacy, not tidiness. This ledger is committed and the remote is public, so an
        # absolute path publishes the author's home-directory layout. All four were ACCEPTED
        # by the first version.
        "/home/noel/private/notes.md:3",
        "/Users/someone/checkout/src/x.py:1",
        "../../etc/secrets.yaml:1",
        "src/x.py:12\n",  # `$` matched before a trailing newline; `\Z` does not
    ],
)
def test_a_deletes_locator_that_is_not_actionable_is_rejected(tmp_path: Path, deletes: str) -> None:
    """`--deletes` must be openable. The failure this guards is an author who never asked
    the question; a receipt reading "somewhere in worktree.py" is that non-answer with a
    filename attached, and accepting it would make the ledger agree that the work was done."""
    # `match=` is not decoration: a bare `raises(ValueError)` passes when the call fails for
    # the OTHER reason (a rejected --gate), so the test would be invariant over the dimension
    # its own name claims — the count:8 class this whole PLAN is about.
    with pytest.raises(ValueError, match="file:line locator"):
        mutation_receipt.record(_repo(tmp_path), gate=_GATE, deletes=deletes)


@pytest.mark.parametrize(
    "gate",
    [
        "test_no_test_pins_a_leading_step_number",  # bare name — not runnable
        "src/harness_maker/x.py::test_y",  # not under tests/
        "tests/structural/test_x.py",  # file, no node
        "",
        "/home/noel/tests/test_x.py::test_y",  # absolute — same leak as --deletes
        "tests/../../elsewhere/test_x.py::test_y",  # escapes the repo
        "tests/structural/test_x.py::test_y\n",  # trailing newline
    ],
)
def test_a_gate_that_is_not_a_runnable_node_is_rejected(tmp_path: Path, gate: str) -> None:
    with pytest.raises(ValueError, match="runnable pytest node id"):
        mutation_receipt.record(_repo(tmp_path), gate=gate, deletes=_DELETES)


@pytest.mark.parametrize(
    "deletes",
    [
        ".gitignore:74",  # no extension at all — a real gate really depends on this line
        ".github/workflows/release.yml:12",  # `.yml`, absent from the first allowlist
        "Makefile:3",
        "src/harness_maker/x.py:12",
    ],
)
def test_a_locator_without_a_blessed_extension_is_still_accepted(
    tmp_path: Path, deletes: str
) -> None:
    """The first version had an extension allowlist and refused all but the last of these.

    It was found by trying to file a TRUE receipt — `test_replay_corpus_committed.py`
    depends on a `.gitignore` line — and being told the answer was malformed. A validator
    that rejects correct answers to keep out wrong ones is worse than no validator: the
    author's next move is to write a locator that passes instead of the one that is true.
    """
    assert mutation_receipt.record(_repo(tmp_path), gate=_GATE, deletes=deletes).is_file()


def test_a_real_pair_is_accepted(tmp_path: Path) -> None:
    """The negative control — without it the four rejection cases above pass on a validator
    that rejects everything, which would make the receipt impossible to file at all."""
    assert mutation_receipt.record(_repo(tmp_path), gate=_GATE, deletes=_DELETES).is_file()


def test_the_ledger_lands_at_the_base_not_inside_a_worktree(tmp_path: Path) -> None:
    """`codex_ledger` wrote to `Path.cwd()` and its rows were lost at `task-land`.

    A REAL git worktree, not a directory that merely looks like one. The first version of
    this test built `base/.worktrees/some-task` with `mkdir` and passed — against a
    structure where the resolver could not fail, since a fake worktree has no `.git` file
    and no git registration. That fixture is why the private-resolver bug this now guards
    was invisible: a reviewer had to read the code to find it.
    """
    base = tmp_path / "repo"
    base.mkdir()
    for cmd in (
        ["git", "init", "-b", "main", "."],
        ["git", "config", "user.email", "t@e.com"],
        ["git", "config", "user.name", "T"],
    ):
        subprocess.run(cmd, cwd=base, check=True, capture_output=True)
    (base / ".claude").mkdir()
    (base / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    (base / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=base, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=base, check=True, capture_output=True)
    wt = base / ".worktrees" / "some-task"
    subprocess.run(["git", "worktree", "add", str(wt)], cwd=base, check=True, capture_output=True)

    written = mutation_receipt.record(wt, gate=_GATE, deletes=_DELETES)
    assert written == base / _LEDGER, "a receipt filed from a worktree was stranded there"
    assert not (wt / _LEDGER).exists()


def test_concurrent_writers_do_not_lose_rows(tmp_path: Path) -> None:
    """The assertion the atomic-append fix actually needs.

    `test_rows_append` records twice SEQUENTIALLY and asserts 2 rows — which a
    read-then-rewrite implementation also satisfies, so it is invariant over the very
    dimension the fix was made for ([fail:test] assertion-invariant-over-named-dimension,
    count:8 — the class this whole PLAN targets, violated by the change that cites it).

    Real processes, genuinely concurrent, one ledger. Under read-then-`atomic_write` each
    writer reads N and writes N+1, so rows are lost and this goes red.
    """
    repo = _repo(tmp_path)
    n = 12
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "harness_maker.mutation_receipt",
                "record",
                "--root",
                str(repo),
                "--gate",
                _GATE,
                "--deletes",
                f"src/x.py:{i}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for i in range(n)
    ]
    for proc in procs:
        _, err = proc.communicate(timeout=180)
        assert proc.returncode == 0, err.decode()

    rows = _rows(repo)
    assert len(rows) == n, f"expected {n} rows, found {len(rows)} — writers lost rows"
    assert {r["deletes"] for r in rows} == {f"src/x.py:{i}" for i in range(n)}
