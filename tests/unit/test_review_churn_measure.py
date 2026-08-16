"""AC-013 — the churn ratio over pinned endpoints and degenerate files.

The golden table in the machine SPEC is the SSOT; the rows are loaded, never
inlined. Two of its five rows expect a *sentinel* rather than a number
(`excluded-from-denominator`, `excluded-and-recorded`) because the observable
for those is the exclusion record, not a ratio — asserting `ratio is None`
alone would pass for an implementation that silently dropped the file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker.review_churn import (
    EXCLUDED_BINARY,
    EXCLUDED_DELETED,
    ChurnMeasurementError,
    FileChurn,
    collect,
    measure,
    measure_refs,
    pin,
)
from harness_maker.spec_machine import GoldenRow, load_golden_table

_SPEC = Path(__file__).parents[2] / "specs" / "SPEC-review-loop-empirics.machine.yaml"
_ROWS = load_golden_table(_SPEC, "AC-013")


def _entries(row: GoldenRow) -> list[FileChurn]:
    return [
        FileChurn(
            path=f["path"],
            kind=f["kind"],
            added=f["added"],
            deleted=f["deleted"],
            post_loc=f["post_loc"],
        )
        for f in row.input["files"]
    ]


@pytest.mark.parametrize(
    "row",
    _ROWS,
    ids=[str(r.input["files"][0]["kind"]) + f"-{i}" for i, r in enumerate(_ROWS)],
)
def test_churn_ratio_endpoints_and_degenerate_files(row: GoldenRow) -> None:
    result = measure(_entries(row))

    if row.expected == "excluded-from-denominator":
        assert result.ratio is None
        assert result.excluded == (("gone.py", EXCLUDED_DELETED),)
        return
    if row.expected == "excluded-and-recorded":
        assert result.ratio is None
        # Recorded, not merely absent — this is the half a `ratio is None`
        # assertion cannot distinguish from dropping the file on the floor.
        assert result.excluded == (("img.png", EXCLUDED_BINARY),)
        return

    assert result.ratio == pytest.approx(row.expected)
    assert result.excluded == ()


def test_churn_ratio_endpoints_and_degenerate_files_aggregates_by_max_not_mean() -> None:
    """The row-4 case, stated as the wrong implementation it rejects.

    Mean would report 0.5 and a denominator-summing aggregate 0.007 — both below
    any usable threshold, which is exactly how a wholly-rewritten small file used
    to escape.
    """
    result = measure(
        [
            FileChurn("big.py", "modified", added=5, deleted=0, post_loc=5000),
            FileChurn("small.py", "modified", added=30, deleted=30, post_loc=30),
        ]
    )
    assert result.ratio == 1.0
    assert result.max_path == "small.py"


def test_churn_ratio_endpoints_and_degenerate_files_ties_break_on_path() -> None:
    both = [
        FileChurn("z.py", "modified", added=10, deleted=0, post_loc=20),
        FileChurn("a.py", "modified", added=10, deleted=0, post_loc=20),
    ]
    assert measure(both).max_path == "a.py"
    assert measure(list(reversed(both))).max_path == "a.py"


def test_churn_ratio_endpoints_and_degenerate_files_all_excluded_is_not_zero() -> None:
    """A binary-only round measured nothing; `0.0` would read as "no churn"."""
    result = measure([FileChurn("img.png", "binary", added=None, deleted=None, post_loc=None)])
    assert result.ratio is None
    assert result.max_path is None
    assert result.as_record() == {
        "churn_ratio": None,
        "churn_max_path": None,
        "churn_measured_n": 0,
        "churn_excluded_n": 1,
    }


def test_churn_ratio_endpoints_and_degenerate_files_rejects_countless_text_file() -> None:
    with pytest.raises(ChurnMeasurementError):
        measure([FileChurn("x.py", "modified", added=None, deleted=None, post_loc=10)])


# ── the pinned-endpoint half, over a real repository ─────────────────────────


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()


def test_churn_ratio_endpoints_and_degenerate_files_pins_the_two_endpoints(
    tmp_path: Path,
) -> None:
    """The measurement spans pre..post only — an earlier round's edits do not count.

    This is the defect the pinning exists to prevent: measured against the
    cumulative working diff, round 2's ratio would carry round 1's rewrite and
    the gate would never skip.
    """
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")

    stable = "\n".join(f"line {i}" for i in range(100)) + "\n"
    (tmp_path / "stable.py").write_text(stable, encoding="utf-8")
    _commit(tmp_path, "base")

    # Round 1 rewrites the file wholly.
    (tmp_path / "stable.py").write_text(
        "\n".join(f"rewritten {i}" for i in range(100)) + "\n", encoding="utf-8"
    )
    pre = _commit(tmp_path, "round 1 fixes")

    # Round 2 touches two of its lines and adds a file.
    text = (tmp_path / "stable.py").read_text(encoding="utf-8").split("\n")
    text[0] = "tweaked"
    (tmp_path / "stable.py").write_text("\n".join(text), encoding="utf-8")
    (tmp_path / "new.py").write_text("a\nb\n", encoding="utf-8")
    post = _commit(tmp_path, "round 2 fixes")

    round2 = measure_refs(tmp_path, pre, post)
    # `new.py` is created → 1.0 dominates; `stable.py` contributes 2/100.
    per_file = dict(round2.measured)
    assert per_file["new.py"] == 1.0
    assert per_file["stable.py"] == pytest.approx(0.02)
    assert round2.ratio == 1.0

    # The same trees measured from the base would carry round 1's rewrite.
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD~2"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()
    cumulative = dict(measure_refs(tmp_path, base, post).measured)
    assert cumulative["stable.py"] == 1.0  # the contamination the pinning excludes


def test_churn_ratio_endpoints_and_degenerate_files_pins_uncommitted_fixes(
    tmp_path: Path,
) -> None:
    """The endpoints a round actually has are dirty trees, not commits.

    `/hm:review` never commits — wrapup does. Pinning `HEAD` twice would measure
    0.0 for every round however much the fixes changed, so the gate would skip
    the re-review unconditionally. This is the whole reason `pin` exists.
    """
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("\n".join(f"l{i}" for i in range(50)) + "\n", encoding="utf-8")
    head = _commit(tmp_path, "base")

    pre = pin(tmp_path, "slug", "r2-pre")
    # An uncommitted repair round: replace 10 of 50 lines (10 added + 10 deleted
    # over a 50-line post tree = 0.4), and add an untracked file.
    (tmp_path / "a.py").write_text(
        "\n".join(f"fixed{i}" for i in range(10))
        + "\n"
        + "\n".join(f"l{i}" for i in range(10, 50))
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "b.py").write_text("x\n", encoding="utf-8")
    post = pin(tmp_path, "slug", "r2-post")

    assert pre != post
    result = measure_refs(tmp_path, pre, post)
    per_file = dict(result.measured)
    assert per_file["a.py"] == pytest.approx(0.4)
    assert per_file["b.py"] == 1.0  # untracked-then-added still counts

    # The same round measured HEAD-to-HEAD sees nothing.
    assert measure_refs(tmp_path, head, head).ratio is None


def test_churn_ratio_endpoints_and_degenerate_files_classifies_git_kinds(
    tmp_path: Path,
) -> None:
    """Deleted, binary and renamed files survive the git adapter with their kinds."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")

    (tmp_path / "gone.py").write_text("x\n" * 90, encoding="utf-8")
    (tmp_path / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02")
    (tmp_path / "old.py").write_text("\n".join(f"l{i}" for i in range(60)) + "\n", encoding="utf-8")
    pre = _commit(tmp_path, "base")

    (tmp_path / "gone.py").unlink()
    (tmp_path / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\xfd\xfc")
    _git(tmp_path, "mv", "old.py", "moved.py")
    post = _commit(tmp_path, "round")

    kinds = {e.path: e.kind for e in collect(tmp_path, pre, post)}
    assert kinds["gone.py"] == "deleted"
    assert kinds["img.png"] == "binary"
    assert kinds["moved.py"] == "renamed"

    excluded = dict(measure_refs(tmp_path, pre, post).excluded)
    assert excluded["gone.py"] == EXCLUDED_DELETED
    assert excluded["img.png"] == EXCLUDED_BINARY


# ── the shipped entry point, not just the functions behind it ────────────────


def test_churn_ratio_endpoints_and_degenerate_files_through_the_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hm review_churn pin|measure` end to end.

    A unit test on `measure()` does not exercise the entry point the stage actually
    calls ([fail:test] shipped-entry-point-not-exercised, count:4).
    """
    import json

    from harness_maker.review_churn import main

    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("\n".join(f"l{i}" for i in range(20)) + "\n", encoding="utf-8")
    _commit(tmp_path, "base")

    assert main(["pin", "--slug", "s", "--label", "r1-pre", "--root", str(tmp_path)]) == 0
    (tmp_path / "a.py").write_text("\n".join(f"l{i}" for i in range(24)) + "\n", encoding="utf-8")
    assert main(["pin", "--slug", "s", "--label", "r1-post", "--root", str(tmp_path)]) == 0
    capsys.readouterr()

    rc = main(
        [
            "measure",
            "--pre",
            "refs/hm-churn/v1/s-r1-pre",
            "--post",
            "refs/hm-churn/v1/s-r1-post",
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["churn_ratio"] == pytest.approx(4 / 24)
    assert payload["churn_max_path"] == "a.py"
    assert payload["measured"] == [{"path": "a.py", "ratio": pytest.approx(4 / 24)}]


def test_churn_cli_reports_a_bad_ref_instead_of_reporting_zero_churn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A misspelled endpoint must not read as "nothing changed" — that silently skips work."""
    from harness_maker.review_churn import main

    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    _commit(tmp_path, "base")

    assert main(["measure", "--pre", "refs/nope", "--post", "HEAD", "--root", str(tmp_path)]) == 1
    assert "measurement failed" in capsys.readouterr().err
