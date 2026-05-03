"""Unit tests for harness_maker.worktree (Phase 8 / Task 8.1).

Exercises real git operations inside tmp_path — the lifecycle is small enough
that mocking git would be more brittle than the real thing. Each test sets up
its own one-commit repo so they remain independent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker import worktree


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(  # noqa: S603 — fixed args, no shell
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Initialize a real git repo with one commit on `main`."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(["init", "-b", "main"], cwd=r)
    _git(["config", "user.email", "test@example.com"], cwd=r)
    _git(["config", "user.name", "Test"], cwd=r)
    (r / "README.md").write_text("# repo\n")
    _git(["add", "."], cwd=r)
    _git(["commit", "-m", "init"], cwd=r)
    return r


def test_create_returns_path_and_directory_exists(repo: Path) -> None:
    wt = worktree.create("execute", repo)
    assert wt.exists()
    assert wt.is_dir()
    assert wt.parent.name == worktree.WORKTREE_DIR_NAME
    assert wt.name.startswith("execute-")


def test_create_generates_unique_branch(repo: Path) -> None:
    wt = worktree.create("dev", repo)
    cp = subprocess.run(  # noqa: S603
        ["git", "branch", "--list"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    branch = wt.name
    assert branch in cp.stdout


def test_cleanup_on_success_removes_directory(repo: Path) -> None:
    wt = worktree.create("execute", repo)
    assert wt.exists()
    worktree.cleanup(wt, on_success=True)
    assert not wt.exists()


def test_cleanup_on_failure_preserves_dirty_worktree(repo: Path) -> None:
    """Non-force cleanup must leave a dirty worktree intact for inspection."""
    wt = worktree.create("execute", repo)
    (wt / "scratch.txt").write_text("uncommitted\n")
    # Should not raise even though cleanup itself fails internally.
    worktree.cleanup(wt, on_success=False)
    # Worktree directory still present because git refused to remove dirty WT.
    assert wt.exists()


def test_merge_squash_brings_worktree_changes_into_base(repo: Path) -> None:
    wt = worktree.create("execute", repo)
    # Make a commit inside the worktree.
    (wt / "feature.txt").write_text("feature\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "feature"], cwd=wt)
    # Merge back.
    worktree.merge(wt, strategy="squash")
    assert (repo / "feature.txt").exists()


def test_cleanup_all_removes_every_worktree(repo: Path) -> None:
    wt1 = worktree.create("execute", repo)
    # Force a different timestamp by switching minute is overkill; just create
    # a second worktree manually so we exercise the multi-removal path.
    wt2_path = repo / worktree.WORKTREE_DIR_NAME / "execute-manual"
    subprocess.run(  # noqa: S603
        ["git", "worktree", "add", "-b", "execute-manual", str(wt2_path)],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    assert wt1.exists()
    assert wt2_path.exists()
    count = worktree.cleanup_all(repo, force=True)
    assert count == 2
    assert not wt1.exists()
    assert not wt2_path.exists()


def test_cleanup_all_returns_zero_when_empty(repo: Path) -> None:
    assert worktree.cleanup_all(repo, force=True) == 0


def test_create_inside_nonrepo_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="git command failed"):
        worktree.create("execute", tmp_path)
