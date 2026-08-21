"""PLAN-bench-study-adoption Phase 3 — size and complexity beside the compliance verdict.

`Ecro/harness-bench`'s `docs/STUDY-ko.md` measured ten arms over 47 review rounds in which the
compliance verdict was **identical** (19/19) while complexity diverged −17% against +58%. No
signal this harness already records could separate those arms: `review_churn` measures churn,
and churn counts edits, not what the edits did to the code.

Three contracts carry the whole phase, and each exists because its absent case has a name:

* **`null` must never mean three things.** A row whose `complexity` is null could mean "not a
  Python file", "the file did not parse", or "measured, and it is zero". Collapsing them makes
  an unsupported language read as a perfectly simple one — `[fail:design] absent-case =
  feature black hole`, count:8 in this repo. `complexity_status` is therefore a three-valued
  enum and cyclomatic complexity starts at 1, so a *measured* zero cannot occur.

* **Both endpoints, not one.** `review_churn.FileChurn` carries `post_loc` only; the pre side
  exists as numstat added/deleted, which is not a line count. A delta needs both, and the
  planning draft asserted this plumbing already existed. It does not.

* **Determinism.** These rows are compared across tasks and weeks. A metric that varies with
  dict ordering or filesystem order makes every comparison noise.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness_maker.review_complexity import (
    Metrics,
    analyze,
    complexity_row,
    record_row,
)

# ── AST metrics ─────────────────────────────────────────────────────────────

_FLAT = "def f(a):\n    return a + 1\n"
_BRANCHY = """
def f(a, b):
    if a:
        for x in b:
            if x:
                return x
    try:
        return a
    except ValueError:
        return None
"""


def test_a_straight_line_function_has_complexity_one_not_zero() -> None:
    """1, never 0 — this is what makes `null` unambiguous elsewhere.

    If a measured file could score 0, a reader could not tell it apart from a file that was
    never measured, and the three-valued `complexity_status` would be carrying a distinction
    the number itself quietly destroys.
    """
    m = analyze(_FLAT)
    assert m.cyclomatic == 1
    assert m.max_nesting == 0


def test_branches_loops_and_handlers_all_raise_complexity() -> None:
    """Rejects a counter wired to only one node type.

    An implementation counting `If` alone passes a single-branch fixture and reports a nested
    loop-and-handler function as simple — which is exactly the direction that would have made
    the study's −17%/+58% split invisible.
    """
    m = analyze(_BRANCHY)
    assert m.cyclomatic >= 5
    assert m.max_nesting >= 3


def test_boolean_operators_count_as_branches() -> None:
    """`if a and b` has two conditions and two ways to fail, not one."""
    assert analyze("def f(a, b):\n    return a and b\n").cyclomatic > analyze(_FLAT).cyclomatic


def test_the_longest_function_is_reported_not_the_file_length() -> None:
    src = "def short():\n    pass\n\n\ndef long_one():\n" + "    x = 1\n" * 20
    assert analyze(src).max_function_lines >= 21


def test_analysis_is_deterministic_across_runs() -> None:
    """These rows are compared across weeks; an order-dependent metric makes that noise."""
    assert analyze(_BRANCHY) == analyze(_BRANCHY)


# ── the row: three-valued status, both endpoints ────────────────────────────


def test_a_python_file_is_measured_at_both_endpoints() -> None:
    row = complexity_row("src/x.py", pre_src=_FLAT, post_src=_BRANCHY)
    assert row["complexity_status"] == "measured"
    assert row["pre_loc"] == len(_FLAT.splitlines())
    assert row["post_loc"] == len(_BRANCHY.splitlines())
    assert row["pre_complexity"]["cyclomatic"] == 1
    assert row["post_complexity"]["cyclomatic"] >= 5


def test_a_non_python_file_reports_loc_and_an_explicit_not_python_status() -> None:
    """The accepted cost of ADR-001, made legible rather than silent.

    A C or Rust consumer sees LOC only. That is a decision, so the row says so by name — a bare
    null would be indistinguishable from a measurement that came back empty.
    """
    row = complexity_row("src/x.c", pre_src="int main(){}\n", post_src="int main(){\n}\n")
    assert row["complexity_status"] == "not-python"
    assert row["pre_complexity"] is None
    assert row["post_complexity"] is None
    assert row["pre_loc"] == 1
    assert row["post_loc"] == 2


def test_a_python_file_that_does_not_parse_is_distinguishable_from_both() -> None:
    """Third value, third meaning. A syntax error mid-refactor must not read as `not-python`."""
    row = complexity_row("src/x.py", pre_src=_FLAT, post_src="def broken(:\n")
    assert row["complexity_status"] == "unparseable"
    assert row["post_complexity"] is None
    assert row["post_loc"] == 1


def test_an_added_file_has_a_null_pre_endpoint_and_still_reports_post() -> None:
    """Absent-case: a file that did not exist before has no pre side, which is not zero."""
    row = complexity_row("src/x.py", pre_src=None, post_src=_FLAT)
    assert row["pre_loc"] is None
    assert row["pre_complexity"] is None
    assert row["post_loc"] == len(_FLAT.splitlines())
    assert row["complexity_status"] == "measured"


def test_a_deleted_file_has_a_null_post_endpoint() -> None:
    row = complexity_row("src/x.py", pre_src=_FLAT, post_src=None)
    assert row["post_loc"] is None
    assert row["post_complexity"] is None


@pytest.mark.parametrize("status", ["measured", "not-python", "unparseable"])
def test_every_status_value_is_one_of_the_three(status: str) -> None:
    """Pins the enum. A fourth value added without updating both sinks is the drift this stops."""
    from harness_maker.review_complexity import COMPLEXITY_STATUSES

    assert status in COMPLEXITY_STATUSES
    assert len(COMPLEXITY_STATUSES) == 3


# ── the jsonl sink ──────────────────────────────────────────────────────────


def test_the_row_is_appended_with_slug_and_round_identity(tmp_path: Path) -> None:
    """ADR-002's trend half. Without slug and round the rows cannot be read as a series.

    The study's conclusion came only from reading across 47 rounds; a sink whose rows cannot be
    grouped answers "what did this round cost" and nothing else, which is the report's job.
    """
    out = record_row(tmp_path, slug="t", round_n=2, files=[complexity_row("a.py", None, _FLAT)])
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 1
    assert rows[0]["slug"] == "t"
    assert rows[0]["round"] == 2
    assert rows[0]["files"][0]["path"] == "a.py"


def test_appending_twice_keeps_both_rows(tmp_path: Path) -> None:
    """Append, never truncate — a rewriting sink silently discards the series it exists for."""
    record_row(tmp_path, slug="t", round_n=1, files=[])
    out = record_row(tmp_path, slug="t", round_n=2, files=[])
    assert len([x for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]) == 2


def test_the_sink_lives_under_the_observability_directory(tmp_path: Path) -> None:
    """It is harness churn, and `_HARNESS_CHURN_PREFIXES` already covers that directory.

    A sink written anywhere else becomes user dirt: `worktree finalize` sweeps it into the
    stash and `worktree create` blocks on it.
    """
    out = record_row(tmp_path, slug="t", round_n=1, files=[])
    assert out.parent.name == "observability"
    assert out.parent.parent.name == ".claude"


def test_a_null_complexity_survives_the_json_round_trip(tmp_path: Path) -> None:
    """`null != 0`, asserted through the sink and not only in memory.

    A serializer that coerced `None` to `0` would put an unsupported language on the same
    footing as a perfectly simple one, in the file that outlives the process.
    """
    out = record_row(tmp_path, slug="t", round_n=1, files=[complexity_row("a.c", "x\n", "y\n")])
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[-1])
    assert row["files"][0]["post_complexity"] is None
    assert row["files"][0]["post_loc"] == 1


def test_metrics_serialize_as_a_mapping_not_a_tuple() -> None:
    """A positional tuple makes the jsonl unreadable the moment a metric is added."""
    assert complexity_row("a.py", None, _FLAT)["post_complexity"] == {
        "cyclomatic": 1,
        "max_nesting": 0,
        "max_function_lines": 2,
    }


def test_metrics_is_frozen() -> None:
    with pytest.raises((AttributeError, TypeError)):
        analyze(_FLAT).cyclomatic = 99  # type: ignore[misc]


def test_metrics_equality_is_by_value() -> None:
    assert Metrics(1, 0, 2) == Metrics(1, 0, 2)


# ── the entry point the stage actually calls ────────────────────────────────
#
# Phase A.5 round 1 blocked on this being absent. The row-shape tests above are library-level,
# and the PLAN's Phase 3 exit criterion (a) says in as many words that a library-level test
# "would pass over a dead verb". The only test that satisfied (a) was INTEGRATION=1-gated and
# therefore did not run in a default `pytest`, which is the same as not existing for every gate
# that matters.
#
# The gate was also wrong on its own terms: CLAUDE.md:136 scopes `INTEGRATION=1` to EXTERNAL
# APIs (arxiv, GitHub, OSV.dev). This shells out to local `git`, and the repo already tests the
# sibling verbs that way ungated — `test_review_churn_measure.py:250`, whose docstring names
# `[fail:test] shipped-entry-point-not-exercised, count:4`. That is this defect's own class.


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)


def _fixture_repo(root: Path) -> str:
    """A two-commit repo whose one Python file gets measurably more complex. Returns the pre ref."""
    (root / "src").mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "src" / "m.py").write_text(_FLAT, encoding="utf-8")
    (root / "notes.md").write_text("hello\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "pre")
    pre = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()
    (root / "src" / "m.py").write_text(_BRANCHY, encoding="utf-8")
    (root / "notes.md").write_text("hello\nworld\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "post")
    return pre


def test_the_cli_verb_measures_and_writes_the_sink(tmp_path: Path) -> None:
    """`hm review_churn complexity` end to end, in-process, no INTEGRATION gate.

    This is the assertion that fails if the verb parses its flags and then reaches the wrong
    function, no-ops before `record_row`, or writes to a path nothing reads — none of which any
    library-level test above can see.
    """
    from harness_maker.review_churn import main

    pre = _fixture_repo(tmp_path)
    rc = main(
        [
            "complexity",
            "--pre",
            pre,
            "--post",
            "HEAD",
            "--slug",
            "demo",
            "--round",
            "2",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0

    ledger = tmp_path / ".claude" / "observability" / "review-complexity.jsonl"
    assert ledger.is_file(), "the verb returned 0 but wrote no sink"
    rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 1
    assert rows[0]["slug"] == "demo"
    assert rows[0]["round"] == 2

    touched = {f["path"]: f for f in rows[0]["files"]}
    py = touched["src/m.py"]
    assert py["complexity_status"] == "measured"
    assert py["pre_complexity"]["cyclomatic"] == 1
    assert py["post_complexity"]["cyclomatic"] >= 5
    assert py["pre_loc"] == len(_FLAT.splitlines())
    assert py["post_loc"] == len(_BRANCHY.splitlines())


def test_the_cli_records_a_non_python_file_as_not_python_rather_than_omitting_it(
    tmp_path: Path,
) -> None:
    """ADR-001's accepted cost has to be VISIBLE in the sink, not silently dropped.

    A row that omits every non-Python file reads as "this round touched only Python", which is
    a different and false statement about the round.
    """
    from harness_maker.review_churn import main

    pre = _fixture_repo(tmp_path)
    assert (
        main(
            [
                "complexity",
                "--pre",
                pre,
                "--post",
                "HEAD",
                "--slug",
                "demo",
                "--round",
                "1",
                "--root",
                str(tmp_path),
            ]
        )
        == 0
    )
    ledger = tmp_path / ".claude" / "observability" / "review-complexity.jsonl"
    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    md = {f["path"]: f for f in row["files"]}["notes.md"]
    assert md["complexity_status"] == "not-python"
    assert md["post_complexity"] is None
    assert md["post_loc"] == 2


# ── round-1 review repairs ──────────────────────────────────────────────────
#
# Each of these exists because a live `/hm:review` found the defect it names. They are written
# so that the pre-repair code fails them, not so that the post-repair code passes.


def test_a_binary_file_in_the_diff_does_not_kill_the_command(tmp_path: Path) -> None:
    """P0, asserted at the layer where it actually happens — the CLI, not `complexity_row`.

    The crash was in `_blob`, which read through the text-mode `_git`: `UnicodeDecodeError` is
    not `CalledProcessError`, so it escaped both that except and `main`'s. It fires BEFORE
    `complexity_row` is ever called.

    A first version of this test passed a `bytes` payload straight to `complexity_row` and
    **passed against the unrepaired code** — `ast.parse` on undecodable bytes raises
    `SyntaxError`, which the old `_endpoint` already caught. That is the fourth instance of the
    confound this review found three times elsewhere: an assertion answering a question about
    the wrong layer. Kept in the record because catching it needed the same discipline the
    review applied to the code.
    """
    from harness_maker.review_churn import main

    pre = _fixture_repo(tmp_path)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)))
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "binary")

    rc = main(
        [
            "complexity",
            "--pre",
            pre,
            "--post",
            "HEAD",
            "--slug",
            "bin",
            "--round",
            "1",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0, "one binary file must not take the round's telemetry down with it"

    ledger = tmp_path / ".claude" / "observability" / "review-complexity.jsonl"
    touched = {
        f["path"]: f
        for r in (
            json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()
        )
        for f in r["files"]
    }
    assert touched["assets/logo.png"]["complexity_status"] == "not-python"
    assert "src/m.py" in touched, "the other files in the round must still be measured"


def test_a_renamed_python_file_keeps_its_pre_endpoint(tmp_path: Path) -> None:
    """P1. `_parse_name_status` drops a rename's old path, so the pre side read a name that
    did not exist at `pre_ref` — reporting `measured` with a null pre side, i.e. "complexity
    appeared from nothing" for a file that only moved.

    Two reviewers found this independently and no test had a rename fixture.
    """
    from harness_maker.review_churn import main

    _fixture_repo(tmp_path)
    # The rename must be the ONLY change in the range, or git's similarity detection
    # correctly reports delete+add and the fixture stops describing a rename at all. A first
    # version diffed from `_fixture_repo`'s pre ref, across which the content also went from
    # 2 lines to 10 — no `R` record, and the test failed for a reason unrelated to the defect.
    pre = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()
    _git(tmp_path, "mv", "src/m.py", "src/renamed.py")
    _git(tmp_path, "commit", "-qm", "rename only")

    assert (
        main(
            [
                "complexity",
                "--pre",
                pre,
                "--post",
                "HEAD",
                "--slug",
                "mv",
                "--round",
                "1",
                "--root",
                str(tmp_path),
            ]
        )
        == 0
    )
    ledger = tmp_path / ".claude" / "observability" / "review-complexity.jsonl"
    touched = {
        f["path"]: f
        for r in (
            json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()
        )
        for f in r["files"]
    }
    entry = touched["src/renamed.py"]
    assert entry["pre_loc"] is not None, "a moved file existed before; its pre side is not absent"
    assert entry["pre_complexity"] == entry["post_complexity"], "a pure rename changes nothing"


def test_a_non_python_binary_stays_not_python_rather_than_unparseable() -> None:
    """The two reasons must not collapse: a PNG is not a broken Python file."""
    row = complexity_row("assets/logo.png", pre_src=None, post_src=b"\x89PNG\xff\xfe")
    assert row["complexity_status"] == "not-python"


def test_utf8_bytes_are_measured_exactly_like_the_same_text() -> None:
    """Discrimination: without this, "treat every bytes input as unparseable" would pass above."""
    assert complexity_row("a.py", None, _FLAT.encode()) == complexity_row("a.py", None, _FLAT)


def test_deeply_nested_source_is_unparseable_rather_than_a_crash() -> None:
    """P1. `_endpoint` caught only `SyntaxError`; `RecursionError` is not one.

    `ast.parse` and `_nesting_depth`'s own recursion both hit the ceiling on generated source.
    """
    row = complexity_row("src/x.py", None, "x = " + "[" * 200 + "]" * 200 + "\n")
    assert row["complexity_status"] in {"measured", "unparseable"}  # never an exception
    if row["complexity_status"] == "unparseable":
        assert row["post_complexity"] is None


def test_a_round_larger_than_one_line_is_split_and_keeps_every_file(tmp_path: Path) -> None:
    """P1. `record_row` hand-rolled a write loop past the size the helper refuses to write.

    `io_utils.append_atomic_line`'s docstring names this caller — "new ledgers import this one"
    — and raises above PIPE_BUF rather than emitting a line the kernel may split. This task's
    own diff touched 40 files, comfortably past it, on a GLOBAL sink every concurrent session
    appends to. Splitting keeps the round in the series instead of losing it to the raise.
    """
    files = [complexity_row(f"src/pkg/module_number_{i:03d}.py", None, _BRANCHY) for i in range(60)]
    out = record_row(tmp_path, slug="big", round_n=1, files=files)

    lines = [x for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) > 1, "a 60-file round must not be one oversized line"
    for line in lines:
        assert len(line.encode("utf-8")) + 1 <= 4096, "every emitted line must fit PIPE_BUF"

    rows = [json.loads(x) for x in lines]
    assert {r["slug"] for r in rows} == {"big"}
    assert {r["round"] for r in rows} == {1}
    recovered = [f["path"] for r in rows for f in r["files"]]
    assert recovered == [f["path"] for f in files], "splitting must lose and reorder nothing"


def test_a_small_round_is_still_exactly_one_line(tmp_path: Path) -> None:
    """Discrimination: without this, splitting every entry into its own line would pass above."""
    files = [complexity_row("a.py", None, _FLAT), complexity_row("b.py", None, _FLAT)]
    out = record_row(tmp_path, slug="small", round_n=1, files=files)
    assert len([x for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]) == 1
