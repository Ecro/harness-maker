"""SPEC-review-effect-measurement — wrapup_land records one review row under --base (AC-002/003)."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker import review_effect as re_mod
from harness_maker import worktree as wt
from harness_maker import wrapup_land
from harness_maker.spec_machine import load_golden_table

_YAML = (
    Path(__file__).resolve().parents[2] / "specs" / "SPEC-review-effect-measurement.machine.yaml"
)

_TABLE = (
    "| id | severity | file:line | finding | disposition | authority |\n|---|---|---|---|---|---|\n"
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    base = tmp_path / "base"
    base.mkdir()
    _git(base, "init", "-b", "main")
    _git(base, "config", "user.email", "t@example.com")
    _git(base, "config", "user.name", "T")
    (base / "README.md").write_text("x\n", encoding="utf-8")
    (base / ".gitignore").write_text(".claude/observability/\n.worktrees/\n", encoding="utf-8")
    _git(base, "add", "-A")
    _git(base, "commit", "-m", "init")
    return base


@pytest.fixture
def task_wt(repo: Path) -> Path:
    target = repo / ".worktrees" / "foo"
    _git(repo, "worktree", "add", "-b", "hm/foo", str(target))
    return target


@pytest.fixture(autouse=True)
def _inert_pop_and_drain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    monkeypatch.setattr(wt, "_cli_drain", lambda _a: 0)


def _args(worktree: Path, base: Path, msg: Path) -> argparse.Namespace:
    return argparse.Namespace(
        worktree=str(worktree),
        base=str(base),
        slug="foo",
        message_file=str(msg),
        required=[],
        optional=["a.md"],
        allow_legacy_ref=False,
        manifest_only=False,
    )


def _msg(tmp_path: Path) -> Path:
    p = tmp_path / "msg.txt"
    p.write_text("feat: foo\n\nbody\n", encoding="utf-8")
    return p


def _review(severity: str, disposition: str) -> str:
    return (
        f"# REVIEW\n\n## Findings\n\n{_TABLE}| F1 | {severity} | a.py:1 | x | {disposition} | |\n"
    )


def _rows(root: Path) -> list[dict[str, Any]]:
    p = root / ".claude" / "observability" / "review-effect.jsonl"
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


_FILES: list[dict[str, str]] = [
    {"REVIEW-foo-2026-10-17.md": _review("P1", "accepted")},
    {},
    {
        "REVIEW-foo-extra-2026-10-17.md": _review("P0", "accepted"),
        "REVIEW-foo-2026-10-16.md": "# REVIEW\n\n## Findings\n\nnone\n",
        "REVIEW-foo-2026-10-17.md": _review("P2", "accepted"),
    },
    {"REVIEW-foo-2026-10-17.md": _review("P1", "accepted")},
]


@pytest.mark.parametrize(
    ("row", "files", "twice"),
    [
        (r, f, bool(r.input.get("run_twice_via_already_present")))
        for r, f in zip(load_golden_table(_YAML, "AC-002"), _FILES, strict=True)
    ],
)
def test_ac_002_land_records_review_row(
    row: Any,
    files: dict[str, str],
    twice: bool,
    repo: Path,
    task_wt: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs = task_wt / "work-docs"
    docs.mkdir()
    for name, body in files.items():
        (docs / name).write_text(body, encoding="utf-8")
    (task_wt / "a.md").write_text("a\n", encoding="utf-8")
    msg = _msg(tmp_path)
    if twice:
        monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 1)
        rc1, r1 = wrapup_land.run(_args(task_wt, repo, msg))
        assert r1["steps"]["commit"]["status"] == "created"
        monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    rc, receipt = wrapup_land.run(_args(task_wt, repo, msg))
    assert rc == wrapup_land.EXIT_OK
    assert "review_effect" in receipt["steps"]

    exp = row.expected
    rows = [r for r in _rows(repo) if r["event"] == "review"]
    assert len(rows) == exp["rows_under_base"]
    if "rows_under_worktree" in exp:
        assert len(_rows(task_wt)) == exp["rows_under_worktree"]
    got = rows[0]
    assert got["slug"] == "foo"
    assert got["commit"] == _git(task_wt, "rev-parse", "HEAD")
    for key in ("status", "severe_accepted", "review_file"):
        if key in exp:
            assert got[key] == exp[key]


def test_ac_003_ledger_failure_never_changes_land(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcomes = []
    for broken in (False, True):
        root = tmp_path / ("b" if broken else "a")
        root.mkdir()
        base = root / "base"
        base.mkdir()
        _git(base, "init", "-b", "main")
        _git(base, "config", "user.email", "t@example.com")
        _git(base, "config", "user.name", "T")
        (base / "README.md").write_text("x\n", encoding="utf-8")
        _git(base, "add", "-A")
        _git(base, "commit", "-m", "init")
        target = base / ".worktrees" / "foo"
        _git(base, "worktree", "add", "-b", "hm/foo", str(target))
        (target / "work-docs").mkdir()
        (target / "work-docs" / "REVIEW-foo-2026-10-17.md").write_text(
            _review("P1", "accepted"), encoding="utf-8"
        )
        (target / "a.md").write_text("a\n", encoding="utf-8")
        if broken:

            def _boom(*_a: Any, **_k: Any) -> None:
                raise OSError("disk full")

            monkeypatch.setattr(re_mod, "append_atomic_line", _boom)
        rc, receipt = wrapup_land.run(_args(target, base, _msg(root)))
        tree = _git(target, "rev-parse", "HEAD^{tree}")
        outcomes.append((rc, tree, receipt["steps"]["review_effect"]["status"]))
    (rc_a, tree_a, st_a), (rc_b, tree_b, st_b) = outcomes
    assert rc_a == rc_b == wrapup_land.EXIT_OK
    assert tree_a == tree_b
    assert st_a == "written"
    assert st_b == "error"


def test_ac_002_unparseable_warns_once(
    repo: Path, task_wt: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docs = task_wt / "work-docs"
    docs.mkdir()
    (docs / "REVIEW-foo-2026-10-17.md").write_text(
        f"# REVIEW\n\n## Verification\n\n{_TABLE}| F1 | P0 | a.py:1 | x | accepted | |\n",
        encoding="utf-8",
    )
    (task_wt / "a.md").write_text("a\n", encoding="utf-8")
    rc, receipt = wrapup_land.run(_args(task_wt, repo, _msg(tmp_path)))
    assert rc == wrapup_land.EXIT_OK
    assert receipt["steps"]["review_effect"]["row_status"] == "unparseable"
    rows = [r for r in _rows(repo) if r["event"] == "review"]
    assert [r["status"] for r in rows] == ["unparseable"]
    assert capsys.readouterr().err.count("review_effect:") == 1
