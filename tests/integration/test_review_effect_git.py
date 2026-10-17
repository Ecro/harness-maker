"""SPEC-review-effect-measurement — escape-candidates (AC-004) and seed (AC-008) on real repos."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_maker import review_effect as re_mod
from harness_maker.spec_machine import load_golden_table

_YAML = (
    Path(__file__).resolve().parents[2] / "specs" / "SPEC-review-effect-measurement.machine.yaml"
)


def _git(root: Path, *args: str, date: str | None = None) -> str:
    env = dict(os.environ)
    if date is not None:
        env["GIT_COMMITTER_DATE"] = date
        env["GIT_AUTHOR_DATE"] = date
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True, env=env
    ).stdout.strip()


def _init(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init", date="2026-10-17T08:00:00Z")
    return root


def _commit(root: Path, files: dict[str, str], subject: str, date: str) -> str:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", subject, date=date)
    return _git(root, "rev-parse", "HEAD")


def _write_ledger(
    root: Path, rows: list[dict[str, Any]], exclusions: list[dict[str, str]] | None = None
) -> None:
    obs = root / ".claude" / "observability"
    obs.mkdir(parents=True, exist_ok=True)
    (obs / "review-effect.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    if exclusions is not None:
        (obs / ".ledger-exclusions.json").write_text(json.dumps(exclusions), encoding="utf-8")


def _review_row(slug: str, ts: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event": "review",
        "ts": ts,
        "slug": slug,
        "harness_version": "0",
        "commit": "x",
        "review_file": None,
        "status": "parsed",
        "counts": {},
        "severe_accepted": 0,
        "unrecognized_n": 0,
    }


_BAR_V1 = (
    "def bar(xs):\n    total = 0\n    for i in range(len(xs) - 1):\n"
    "        total += xs[i]\n    return total\n"
)
_BAR_V2 = (
    "def bar(xs):\n    total = 0\n    for i in range(len(xs)):\n"
    "        total += xs[i]\n    return total\n"
)


def _scenario(idx: int, root: Path) -> dict[str, str]:
    """Build golden row `idx`'s repo; returns name → sha for the commits it planted."""
    shas: dict[str, str] = {}
    if idx == 0:
        shas["c1"] = _commit(
            root,
            {"specs/SPEC-bar.md": "# bar\n", "bar.py": _BAR_V1},
            "feat: bar",
            "2026-10-17T10:00:00Z",
        )
        shas["c2"] = _commit(
            root, {"bar.py": _BAR_V2}, "fix: off-by-one in bar", "2026-10-17T12:00:00Z"
        )
        _write_ledger(root, [_review_row("bar", "2026-10-17T11:00:00Z")])
    elif idx == 1:
        shas["c1"] = _commit(root, {"a.py": "a = 1\n"}, "fix: early", "2026-10-17T09:00:00Z")
        _write_ledger(root, [_review_row("bar", "2026-10-17T11:00:00Z")])
    elif idx == 2:
        _commit(
            root,
            {"specs/SPEC-bar.md": "# bar\n", "bar.py": _BAR_V1},
            "feat: bar",
            "2026-10-17T10:00:00Z",
        )
        shas["c2"] = _commit(
            root,
            {"bar.py": _BAR_V1 + "\n\ndef extra():\n    return 1\n"},
            "fix: add missing helper",
            "2026-10-17T12:00:00Z",
        )
        _write_ledger(root, [_review_row("bar", "2026-10-17T11:00:00Z")])
    elif idx == 3:
        _commit(root, {"a.py": "a = 1\n"}, "fix: something", "2026-10-17T12:00:00Z")
    elif idx == 4:
        shas["early"] = _commit(root, {"a.py": "a = 1\n"}, "fix: between", "2026-10-17T10:30:00Z")
        _write_ledger(
            root,
            [
                _review_row("old", "2026-10-17T09:00:00Z"),
                _review_row("bar", "2026-10-17T11:00:00Z"),
            ],
            [{"key": "slug", "value": "old", "reason": "test"}],
        )
    return shas


@pytest.mark.parametrize(("idx", "row"), list(enumerate(load_golden_table(_YAML, "AC-004"))))
def test_ac_004_escape_candidates(
    idx: int, row: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _init(tmp_path / "repo")
    shas = _scenario(idx, root)
    assert re_mod.main(["escape-candidates", "--root", str(root), "--json"]) == 0
    cap = capsys.readouterr()
    got = json.loads(cap.out)
    exp = row.expected
    commits = [c["commit"] for c in got]
    if isinstance(exp.get("candidates"), list):
        assert commits == [shas[n] for n in exp["candidates"]]
    elif "candidates" in exp:
        assert len(commits) == exp["candidates"]
    if isinstance(exp.get("hint_slugs"), dict):
        for name, slugs in exp["hint_slugs"].items():
            entry = next(c for c in got if c["commit"] == shas[name])
            assert entry["hint_slugs"] == slugs
    elif "hint_slugs" in exp:
        assert all(c["hint_slugs"] == exp["hint_slugs"] for c in got)
    if exp.get("stderr_warning"):
        assert "review_effect" in cap.err
    if "cutoff" in exp:
        # The excluded 09:00 row must not open the window, so the 10:30 fix stays out.
        assert shas["early"] not in commits


def test_ac_004_recorded_escape_is_not_listed_again(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _init(tmp_path / "repo")
    shas = _scenario(0, root)
    argv = [
        "escape",
        "--root",
        str(root),
        "--commit",
        shas["c2"],
        "--verdict",
        "not-escape",
        "--introduced-by",
        "unknown",
        "--flagged",
        "unknown",
        "--reviewable",
        "unknown",
        "--reason",
        "wording",
    ]
    assert re_mod.main(argv) == 0
    capsys.readouterr()
    assert re_mod.main(["escape-candidates", "--root", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


# ── AC-008 ──────────────────────────────────────────────────────────────────

_SRC = [
    "def f{i}(a, b):\n"
    '    """Doc with a < b and 3 inside."""\n'
    "    if a < b and b != {i}:\n"
    "        return a + {i}\n"
    "    return b\n",
    "def g{i}(x):\n    # comment x == 2\n    return x == 2 or x > {i}\n",
]


def _seed_repo(root: Path, n_files: int) -> str:
    _init(root)
    for i in range(n_files):
        (root / f"m{i}.py").write_text("def untouched():\n    return 0 < 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "context")
    base = _git(root, "rev-parse", "HEAD")
    for i in range(n_files):
        body = (root / f"m{i}.py").read_text(encoding="utf-8")
        (root / f"m{i}.py").write_text(
            body + "\n\n" + _SRC[i % 2].format(i=i + 1), encoding="utf-8"
        )
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "task diff")
    return base


def _changed_lines(root: Path, args: list[str]) -> set[tuple[str, int]]:
    out = _git(root, "diff", "-U0", *args)
    lines: set[tuple[str, int]] = set()
    cur = ""
    for ln in out.splitlines():
        if ln.startswith("+++ b/"):
            cur = ln[6:]
        elif ln.startswith("@@"):
            new = ln.split("+", 1)[1].split(" ", 1)[0]
            start, _, count = new.partition(",")
            n = int(count) if count else 1
            lines.update((cur, int(start) + k) for k in range(n))
    return lines


def _docstring_and_comment_lines(root: Path) -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    for p in root.glob("m*.py"):
        for no, text in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if '"""' in text or text.lstrip().startswith("#"):
                out.add((p.name, no))
    return out


@settings(
    max_examples=12, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(n_files=st.integers(1, 5), count=st.integers(1, 5), seed=st.integers(0, 50))
def test_ac_008_seed_is_deterministic_and_inside_the_diff(
    tmp_path_factory: pytest.TempPathFactory, n_files: int, count: int, seed: int
) -> None:
    root = tmp_path_factory.mktemp("seed")
    base = _seed_repo(root, n_files)
    task_lines = _changed_lines(root, [f"{base}..HEAD"])
    skip = _docstring_and_comment_lines(root)

    first = re_mod.seed(root, base=base, count=count, seed=seed)
    assert 1 <= len(first) <= count
    seeded = {(m["file"], m["line"]) for m in first}
    assert seeded == _changed_lines(root, ["HEAD"])
    assert seeded <= task_lines
    assert not (seeded & skip)
    assert {m["operator"] for m in first} <= {"cmp-flip", "boolop-swap", "const-off-by-one"}

    _git(root, "checkout", "--", ".")
    assert re_mod.seed(root, base=base, count=count, seed=seed) == first


def test_ac_008_seed_refuses_a_dirty_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "repo"
    base = _seed_repo(root, 1)
    path = root / "m0.py"
    path.write_text(path.read_text(encoding="utf-8") + "# dirty\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    rc = re_mod.main(["seed", "--root", str(root), "--base", base, "--count", "2", "--seed", "1"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "git checkout --" in err
    assert "worktree add" in err
    assert "untouched" in err
    assert path.read_text(encoding="utf-8") == before


# ── review round 1 regressions ─────────────────────────────────────────────


def test_ac_004_hint_from_root_commit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _commit(
        root,
        {"specs/SPEC-root.md": "# r\n", "a.py": "x = 1\n"},
        "feat: root",
        "2026-10-17T10:00:00Z",
    )
    fix = _commit(root, {"a.py": "x = 2\n"}, "fix: x", "2026-10-17T12:00:00Z")
    _write_ledger(root, [_review_row("root", "2026-10-17T11:00:00Z")])
    assert re_mod.main(["escape-candidates", "--root", str(root), "--json"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got == [{**got[0], "commit": fix, "hint_slugs": ["root"]}]


def test_ac_004_unreadable_ts_is_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _init(tmp_path / "repo")
    fix = _commit(root, {"a.py": "a = 1\n"}, "fix: a", "2026-10-17T12:00:00Z")
    _write_ledger(root, [{**_review_row("x", "garbage")}, _review_row("y", "2026-10-17T11:00:00Z")])
    assert re_mod.main(["escape-candidates", "--root", str(root), "--json"]) == 0
    cap = capsys.readouterr()
    assert [c["commit"] for c in json.loads(cap.out)] == [fix]
    assert "unreadable ts" in cap.err


def test_ac_008_multiline_compare_is_a_candidate(tmp_path: Path) -> None:
    root = _init(tmp_path / "repo")
    base = _git(root, "rev-parse", "HEAD")
    _commit(
        root,
        {"w.py": "def f(a, b):\n    return (a <\n            b)\n"},
        "feat: w",
        "2026-10-17T10:00:00Z",
    )
    manifest = re_mod.seed(root, base=base, count=1, seed=0)
    assert [(m["file"], m["line"], m["operator"]) for m in manifest] == [("w.py", 2, "cmp-flip")]
    assert (root / "w.py").read_text(encoding="utf-8").splitlines()[1] == "    return (a <="


def test_ac_008_seed_preserves_file_mode(tmp_path: Path) -> None:
    root = _init(tmp_path / "repo")
    base = _git(root, "rev-parse", "HEAD")
    script = root / "s.py"
    script.write_text("#!/usr/bin/env python3\nprint(1 < 2)\n", encoding="utf-8")
    script.chmod(0o755)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "feat: s")
    assert re_mod.seed(root, base=base, count=1, seed=0)
    assert script.stat().st_mode & 0o777 == 0o755
    assert "old mode" not in _git(root, "diff")


# ── review round 2 regressions ─────────────────────────────────────────────


def test_ac_004_hint_for_a_path_with_a_space(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _init(tmp_path / "repo")
    _commit(
        root,
        {"specs/SPEC-sp.md": "# s\n", "my file.py": "x = 1\n"},
        "feat: sp",
        "2026-10-17T10:00:00Z",
    )
    fix = _commit(root, {"my file.py": "x = 2\n"}, "fix: x", "2026-10-17T12:00:00Z")
    _write_ledger(root, [_review_row("sp", "2026-10-17T11:00:00Z")])
    assert re_mod.main(["escape-candidates", "--root", str(root), "--json"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert [(c["commit"], c["hint_slugs"]) for c in got] == [(fix, ["sp"])]


def test_hunks_ignore_header_lookalikes_inside_a_hunk() -> None:
    diff = (
        "diff --git a/q.sql b/q.sql\nindex 1..2 100644\n--- a/q.sql\n+++ b/q.sql\n"
        "@@ -3 +2,0 @@ x\n--- a comment\n@@ -5,0 +5 @@ y\n+++ more\n"
    )
    assert re_mod._hunks(diff, "old") == [("q.sql", 3, 1), ("q.sql", 5, 0)]
    assert re_mod._hunks(diff, "new") == [("q.sql", 2, 0), ("q.sql", 5, 1)]


def test_ac_008_seed_skips_a_symlinked_py_file(tmp_path: Path) -> None:
    root = _init(tmp_path / "repo")
    base = _git(root, "rev-parse", "HEAD")
    (root / "real.txt").write_text("def f(a, b):\n    return a < b\n", encoding="utf-8")
    (root / "link.py").symlink_to("real.txt")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "feat: link")
    before = (root / "real.txt").read_text(encoding="utf-8")
    assert re_mod.seed(root, base=base, count=3, seed=0) == []
    assert (root / "link.py").is_symlink()
    assert (root / "real.txt").read_text(encoding="utf-8") == before
