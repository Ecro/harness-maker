"""AC-004 — `economics composition` reports what the context is made of, from committed code.

This subcommand exists to make a **prose-only** instruction falsifiable after the fact. The
user chose prose with no enforcement hook (SPEC Accepted Risks), so nothing at runtime will
ever say whether the rules changed behaviour. Re-running this against a later corpus is the
only thing that will, and PLAN ADR-001 requires it to land BEFORE the instruction so the
before/after comparison is committed-code vs committed-code rather than scratchpad vs
committed-code.

The fixture is hand-counted. `duplicate_chars` must equal exactly 100 — the `Write` on
`/proj/a.md`, which was `Read` earlier in the same session, and nothing else:

* the `Write` on `/proj/new.md` (3 chars) is a NEW file — irreducible, must not count;
* the `Write` on `/elsewhere/z.md` (20 chars) is out-of-project — `is_own_cwd` must drop it,
  because the transcript DIRECTORY name is a lossy encoding that a foreign project can
  collide with, and the per-turn cwd is the real boundary (`economics_source:116`).

Both of those are the arms that make the number a measurement rather than a sum.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.economics import main
from harness_maker.economics_source import encode_project_dir

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "composition_session.jsonl"

# Hand-counted from the fixture. Named, not inlined, so a change to either the fixture or
# the expectation is a visible edit to a stated pair.
_DUP_CHARS = 100
_DUP_CALLS = 1
_WRITE_CALLS = 2  # in-project only: a.md + new.md; the /elsewhere one is not this project


@pytest.fixture
def corpus(tmp_path: Path) -> tuple[Path, Path]:
    """A transcript store laid out the way the reader discovers it.

    The directory name is computed by `encode_project_dir`, not committed, because it is a
    function of the project's absolute path — a committed name would only resolve on the
    machine that created it. Same class of defect as
    `[fail:test] snapshot-regen-inside-worktree`.
    """
    project = tmp_path / "proj"
    project.mkdir()
    store = tmp_path / "transcripts"
    session_dir = store / encode_project_dir(project)
    session_dir.mkdir(parents=True)
    # The fixture is committed with a placeholder root. Both the per-turn `cwd` and the
    # `file_path`s must be real absolute paths under the tmp project, for the same reason
    # the directory name is computed: a committed absolute path only resolves on the
    # machine that wrote it. `/elsewhere` is deliberately NOT substituted — it is the
    # out-of-project arm.
    body = _FIXTURE.read_text(encoding="utf-8").replace("/proj", str(project))
    (session_dir / "session.jsonl").write_text(body, encoding="utf-8")
    return project, store


def _run(project: Path, store: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    rc = main(["composition", "--root", str(project), "--transcript-root", str(store)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, dict)
    return payload


def test_the_fixture_is_shaped_as_the_test_assumes(corpus: tuple[Path, Path]) -> None:
    """Positive control — every assertion below is vacuous against an empty store."""
    _, store = corpus
    lines = [
        json.loads(x)
        for x in (next(store.glob("*/session.jsonl"))).read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    assert len(lines) == 11
    assert sum(1 for r in lines if r.get("cwd") == "/elsewhere") == 1


def test_composition_reports_the_three_sections(
    corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-004 first conjunct — the contract the RESEARCH document's three tables need."""
    project, store = corpus
    payload = _run(project, store, capsys)
    assert {"by_category", "by_bash_kind", "write_after_read"} <= set(payload)
    assert payload["by_category"], "by_category is empty — nothing was read"


def test_write_after_read_duplication_is_computed_not_summed(
    corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-004 second conjunct — the non-vacuity arm.

    A subcommand that returned a well-shaped dict of zeros, or that summed every Write,
    would pass the shape check above. This pins the number.
    """
    project, store = corpus
    war = _run(project, store, capsys)["write_after_read"]
    assert isinstance(war, dict)
    assert war["duplicate_chars"] == _DUP_CHARS
    assert war["duplicate_calls"] == _DUP_CALLS
    assert war["write_calls"] == _WRITE_CALLS


def test_a_new_file_write_is_not_counted_as_duplication(
    corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """69% of Write bytes create new files. Counting those would make the metric useless."""
    project, store = corpus
    war = _run(project, store, capsys)["write_after_read"]
    assert isinstance(war, dict)
    assert war["duplicate_chars"] < war["write_chars"], "every Write counted as duplicate"
    assert war["write_chars"] == _DUP_CHARS + 3


def test_turns_from_another_project_are_excluded(
    corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """`is_own_cwd` is the real boundary; the directory name is a lossy encoding.

    The fixture's `/elsewhere` Write is 20 chars. If it leaked in, `write_chars` would be
    123 rather than 103 and the duplication share would be computed over a foreign project.
    """
    project, store = corpus
    war = _run(project, store, capsys)["write_after_read"]
    assert isinstance(war, dict)
    assert war["write_calls"] == _WRITE_CALLS
    assert "Z" * 20 not in json.dumps(war)


def test_bash_output_is_classified_by_command_kind(
    corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The RESEARCH finding that matters is 13.5% search+inspection, which needs the split."""
    project, store = corpus
    kinds = _run(project, store, capsys)["by_bash_kind"]
    assert isinstance(kinds, dict)
    assert "grep/rg" in kinds
    assert "file inspection" in kinds
    # Hand-derived from the fixture, because presence alone is not the contract: the share
    # is. The mutation receipt dropped the tool_use INPUT accounting and left the
    # tool_result accounting, halving every number while both keys stayed present and the
    # test stayed green. Both halves must be counted.
    #   input  dict -> json.dumps({"command": "rg foo src/"})  = 26 chars
    #   result str  -> "match1 match2"                         = 13 chars
    assert kinds["grep/rg"]["chars"] == 26 + 13


def test_an_empty_store_is_reported_not_crashed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fresh clone, CI, or a Cursor/Codex project has no transcripts — the absent case.

    `doctor` already treats this as `status: n/a` rather than an error, and a divide-by-zero
    here would make the subcommand unusable exactly where a user first tries it.
    """
    project = tmp_path / "empty"
    project.mkdir()
    store = tmp_path / "none"
    store.mkdir()
    rc = main(["composition", "--root", str(project), "--transcript-root", str(store)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_chars"] == 0
    assert payload["write_after_read"]["duplicate_chars"] == 0
