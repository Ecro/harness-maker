"""SPEC-bench-wrapup-defects: two defects the 2026-11-25 cost/value bench left in hm's output.

With isolation off the wrapup commit lacked the code (35 of 36 runs), and
`.claude/memory/.wiki.lock` was committed (30 of 36).
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker import worktree as wt
from harness_maker import wrapup_land
from tests._overhaul_p1_ref import HEAD_SRC
from tests.unit import test_overhaul_p1_surface as surface

_STAGE_PHRASE = "`git add` this task's code and tests before it."
_INDEX_PHRASE = "`index_after` must hold the code."


@pytest.fixture(scope="module")
def renders(tmp_path_factory: pytest.TempPathFactory) -> dict[bool, Path]:
    base = tmp_path_factory.mktemp("bench-defects")
    return {
        worktree: surface._make(
            base, f"wt-{worktree}", surface.Arm("Side", "claude-code", worktree), HEAD_SRC
        )
        for worktree in (False, True)
    }


def _stage(project: Path, stage: str) -> str:
    return (project / ".claude" / "commands" / "hm" / f"{stage}.md").read_text(encoding="utf-8")


def test_ac_001_isolation_off_wrapup_stages_the_code_first(renders: dict[bool, Path]) -> None:
    off, on = _stage(renders[False], "wrapup"), _stage(renders[True], "wrapup")
    assert _STAGE_PHRASE in off
    assert _INDEX_PHRASE not in off
    assert _STAGE_PHRASE not in on
    assert _INDEX_PHRASE in on


# ── git fixtures ─────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    base = tmp_path / "base"
    base.mkdir()
    for args in (
        ("init", "-b", "main"),
        ("config", "user.email", "t@example.com"),
        ("config", "user.name", "T"),
    ):
        _git(base, *args)
    (base / "README.md").write_text("x\n", encoding="utf-8")
    _git(base, "add", "README.md")
    _git(base, "commit", "-m", "init")
    (base / "work-docs").mkdir()
    (base / "work-docs" / "PLAN-slug.md").write_text("plan\n", encoding="utf-8")
    return base


@pytest.fixture
def message(tmp_path: Path) -> Path:
    p = tmp_path / "msg.txt"
    p.write_text("feat(x): subject\n\nbody\n", encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _inert_pop_and_drain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    monkeypatch.setattr(wt, "_cli_drain", lambda _a: 0)


def _args(worktree: Path, base: Path, msg: Path, **kw: Any) -> argparse.Namespace:
    values: dict[str, Any] = {
        "worktree": str(worktree),
        "base": str(base),
        "slug": "slug",
        "message_file": str(msg),
        "required": ["work-docs/PLAN-slug.md"],
        "optional": [],
        "allow_legacy_ref": False,
        "manifest_only": False,
    }
    values.update(kw)
    return argparse.Namespace(**values)


def _committed(root: Path) -> set[str]:
    out = _git(root, "show", "--name-only", "--pretty=format:", "HEAD").stdout
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def test_ac_002_the_receipt_lists_what_the_commit_left_out(
    repo: Path, message: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "src").mkdir()
    (repo / "src" / "impl.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "stray.py").write_text("y = 2\n", encoding="utf-8")
    (repo / "a b.py").write_text("w = 4\n", encoding="utf-8")  # porcelain would quote it
    _git(repo, "add", "src/impl.py")

    rc, receipt = wrapup_land.run(_args(repo, repo, message))

    assert rc == 0, receipt
    assert "src/impl.py" in _committed(repo)
    left_out = receipt["steps"]["left_out"]
    assert "stray.py" in left_out
    assert "a b.py" in left_out
    assert "src/impl.py" not in left_out
    assert "[wrapup_land] left out of the commit:" in capsys.readouterr().err

    isolated = repo / ".worktrees" / "slug"
    _git(repo, "worktree", "add", "-b", "hm/slug", str(isolated))
    (isolated / "work-docs" / "PLAN-slug.md").write_text("plan v2\n", encoding="utf-8")
    (isolated / "new.py").write_text("z = 3\n", encoding="utf-8")
    rc, isolated_receipt = wrapup_land.run(_args(isolated, repo, message))
    assert rc == 0, isolated_receipt
    assert isolated_receipt["steps"]["left_out"] == []


def test_ac_003_memory_lock_files_are_ignored_and_never_committed(
    repo: Path, message: Path
) -> None:
    assert ".claude/memory/*.lock" in wt._HARNESS_GITIGNORE_PATTERNS
    wt._ensure_harness_gitignore(repo)
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "gitignore")
    memory = repo / ".claude" / "memory"
    memory.mkdir(parents=True)
    (memory / "wiki.md").write_text("## [wiki:fact] a | 2026-11-25\nbody\n", encoding="utf-8")
    (memory / ".wiki.lock").write_text("", encoding="utf-8")

    assert _git(repo, "check-ignore", "-q", ".claude/memory/.wiki.lock").returncode == 0
    assert _git(repo, "check-ignore", "-q", ".claude/memory/wiki.md").returncode == 1

    rc, receipt = wrapup_land.run(_args(repo, repo, message, optional=[".claude/memory/"]))
    assert rc == 0, receipt
    committed = _committed(repo)
    assert committed == {".claude/memory/wiki.md", "work-docs/PLAN-slug.md"}, committed
    assert not any(re.search(r"\.lock$", p) for p in committed)
