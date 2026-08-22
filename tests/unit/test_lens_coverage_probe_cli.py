"""PLAN-bench-study-adoption Phase 4 — the probe check reached through the actual CLI.

The Testing Strategy names this scenario in as many words: one end-to-end `lens_coverage check`
over a results directory holding one valid and one probe-invalid lens, asserting
`blocks_approval: true` with the invalid lens in `missing`.

It is separate from the library tests for the reason Phase 3 established and this repo names
`[fail:test] shipped-entry-point-not-exercised` (count:4): a verdict function that is correct
and a CLI that never reaches it look identical from the library side. Here that gap is wider
than usual, because the CLI is what has to build `ProbeCheck` from `--diff-files` and `--rev` —
the part no library test can exercise at all.

Ungated deliberately. CLAUDE.md:136 reserves `INTEGRATION=1` for external APIs; this shells out
to local `git`, which the repo already tests ungated (`test_review_churn_measure.py:250`).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

_RUN = "run-cli-1"
_CAUSE = "src/pkg/cause.py"
_CAUSE_BODY = "import os\n\n\ndef reach(flag):\n    return os.sep if flag else None\n"
_TOUCHED = "src/pkg/touched.py"

_MANDATORY = (
    "design",
    "functionality",
    "robustness",
    "consistency",
    "security",
    "concurrency",
    "tests",
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)


def _repo(root: Path) -> str:
    """Two tracked files, one of which the 'diff' touches. Returns the reviewed revision."""
    (root / "src" / "pkg").mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / _CAUSE).write_text(_CAUSE_BODY, encoding="utf-8")
    (root / _TOUCHED).write_text("def touched():\n    return 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()


def _results(root: Path, probes: Mapping[str, object]) -> Path:
    d = root / ".hm-lens-results" / "slug" / _RUN / "1"
    d.mkdir(parents=True)
    for lens in _MANDATORY:
        payload: dict[str, object] = {"lens": lens, "run_id": _RUN, "findings": []}
        if lens in probes:
            payload["repo_probe"] = probes[lens]
        (d / f"{lens}.json").write_text(json.dumps(payload), encoding="utf-8")
    return root / ".hm-lens-results"


def _run(root: Path, results: Path, rev: str, *extra: str) -> subprocess.CompletedProcess[str]:
    from harness_maker import lens_coverage

    diff_list = root / "diff.txt"
    diff_list.write_text(_TOUCHED + "\n", encoding="utf-8")
    argv = [
        "check",
        "--results-dir",
        str(results),
        "--slug",
        "slug",
        "--round",
        "1",
        "--run-id",
        _RUN,
        "--preset",
        "Production",
        "--diff-files",
        str(diff_list),
        "--rev",
        rev,
        "--root",
        str(root),
        *extra,
    ]
    rc = lens_coverage.main(argv)
    return subprocess.CompletedProcess(argv, rc, "", "")


def test_one_valid_and_one_invalid_probe_names_the_invalid_lens(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The scenario the Testing Strategy names, through the entry point the stage calls.

    Renamed from `..._blocks_and_names_...`: the probe went advisory after a live review showed
    it fails on reviewers that HAVE read the repository. It still has to NAME the lens — a
    detector that reports nothing is not advisory, it is absent.
    """
    rev = _repo(tmp_path)
    good = {"path": _CAUSE, "line": 4, "text": "def reach(flag):"}
    bad = {"path": _CAUSE, "line": 4, "text": "def reach(flag, extra):"}
    results = _results(tmp_path, dict.fromkeys(_MANDATORY, good) | {"security": bad})

    _run(tmp_path, results, rev)
    verdict = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    # ADVISORY: the probe failure is reported, the verdict is unmoved. Blocking on it made
    # every Production harness's review permanently unapprovable once it re-rendered.
    assert verdict["probe_failed"] == ["security"]
    assert verdict["blocks_approval"] is False
    assert "design" in verdict["exercised"]
    assert "security" in verdict["exercised"]


def test_all_valid_probes_do_not_block(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Discrimination. Without it, a CLI that rejected everything would satisfy the test above."""
    rev = _repo(tmp_path)
    good = {"path": _CAUSE, "line": 4, "text": "def reach(flag):"}
    results = _results(tmp_path, dict.fromkeys(_MANDATORY, good))

    _run(tmp_path, results, rev)
    verdict = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert verdict["blocks_approval"] is False
    assert verdict["missing"] == []
    assert verdict["probe_failed"] == [], "a valid probe must not be reported as failed"


def test_absent_flags_skip_the_check_loudly_instead_of_failing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ABSENT and EMPTY are different, and only one of them is an error.

    An earlier version made absent flags exit 2. That broke four pre-existing CLI tests, and
    what they were reporting is a real backward-compatibility break: a harness rendered before
    this change has no flags in its `review.md`, so the first review after a package update
    would fail at the coverage gate. Failing an entire Production harness's review is a worse
    outcome than the canary being off for one run.

    "Off" must not be SILENT, which is what the stderr line is for — and it names the remedy,
    because a warning that only reports a symptom leaves the reader where it found them. The
    empty-set half of the contract is untouched; see below.
    """
    from harness_maker import lens_coverage

    _repo(tmp_path)
    results = _results(tmp_path, {})
    rc = lens_coverage.main(
        [
            "check",
            "--results-dir",
            str(results),
            "--slug",
            "slug",
            "--round",
            "1",
            "--run-id",
            _RUN,
            "--preset",
            "Production",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "SKIPPED" in err
    assert "make --update" in err


def test_an_empty_diff_file_list_is_still_a_hard_error(tmp_path: Path) -> None:
    """The half that must NOT degrade.

    An empty list makes "not in the diff" true of every path, so the check would run and pass
    everything — a silent no-op wearing the appearance of a live canary. That is worse than
    skipping, because nothing says it happened.
    """
    from harness_maker import lens_coverage

    rev = _repo(tmp_path)
    results = _results(tmp_path, {})
    empty = tmp_path / "empty.txt"
    empty.write_text("\n  \n", encoding="utf-8")
    rc = lens_coverage.main(
        [
            "check",
            "--results-dir",
            str(results),
            "--slug",
            "slug",
            "--round",
            "1",
            "--run-id",
            _RUN,
            "--preset",
            "Production",
            "--diff-files",
            str(empty),
            "--rev",
            rev,
            "--root",
            str(tmp_path),
        ]
    )
    assert rc != 0


def test_side_runs_without_the_flags_and_does_not_check_probes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-005's Side branch, at the layer that decides it.

    Side renders no probe requirement, so its result files carry none. If the CLI demanded the
    flags — or checked probes without them — every Side review would be permanently
    unapprovable. This is the assertion that fails if the Production requirement leaks.
    """
    from harness_maker import lens_coverage

    _repo(tmp_path)
    results = _results(tmp_path, {})
    rc = lens_coverage.main(
        [
            "check",
            "--results-dir",
            str(results),
            "--slug",
            "slug",
            "--round",
            "1",
            "--run-id",
            _RUN,
            "--preset",
            "Side",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    verdict = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert verdict["blocks_approval"] is False


# ── S12: the content comes from the blob at --rev, never from the working tree ──
#
# Authored in a closed-scope A.5 round (Path A, operator-authorized past the two-round budget).
#
# Every other fixture in this file commits once and never mutates, so working-tree bytes and
# blob-at-`rev` bytes are identical and an implementation doing `open(root / path)` is
# observationally equal to one doing `git show <rev>:<path>`. That equality matters because the
# `--rev` read is not a preference — it is the whole of R11. The probe's `path` is model output,
# and a tracked symlink sits in `git ls-files` while resolving anywhere at all; reading the
# object store cannot follow it, reading the tree can.
#
# The two tests below diverge disk from `rev` in OPPOSITE directions. One alone would not do:
# an implementation that read neither source and simply accepted everything would pass the first,
# and one that rejected everything would pass the second.


def _dirty(root: Path, body: str) -> None:
    """Overwrite the cause file WITHOUT committing, so disk and `rev` disagree."""
    (root / _CAUSE).write_text(body, encoding="utf-8")


def test_a_probe_right_at_rev_and_wrong_on_disk_is_still_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reading the working tree would REJECT this. Reading the blob accepts it.

    The quoted line is what `_CAUSE` held at the reviewed revision; the tree now holds something
    else entirely. A validator that opens the file on disk sees a mismatch and drops the lens.
    """
    rev = _repo(tmp_path)
    good_at_rev = {"path": _CAUSE, "line": 4, "text": "def reach(flag):"}
    results = _results(tmp_path, dict.fromkeys(_MANDATORY, good_at_rev))
    _dirty(tmp_path, "# rewritten after the review point\n" * 8)

    _run(tmp_path, results, rev)
    verdict = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert verdict["missing"] == [], (
        "a probe quoting the reviewed revision was rejected — the validator is reading the "
        "working tree, which is the arbitrary-file-reader path R11 exists to close"
    )
    assert verdict["blocks_approval"] is False


def test_a_probe_right_on_disk_and_wrong_at_rev_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction, and the one an attacker would use.

    The tree is edited so the quoted text matches what is on disk **now** while matching nothing
    at the reviewed revision. A validator reading the tree accepts it; one reading the blob does
    not. Without this arm, an implementation that read neither source and accepted every probe
    would satisfy the test above.
    """
    rev = _repo(tmp_path)
    planted = "def planted_by_the_probe_author():\n"
    _dirty(tmp_path, planted)
    good_on_disk = {"path": _CAUSE, "line": 1, "text": planted.rstrip("\n")}
    results = _results(tmp_path, dict.fromkeys(_MANDATORY, good_on_disk))

    _run(tmp_path, results, rev)
    verdict = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert sorted(verdict["probe_failed"]) == sorted(_MANDATORY), (
        "a probe matching only the post-review working tree verified — the validator is "
        "reading the tree, so the quoted 'evidence' never had to exist at the reviewed revision"
    )
