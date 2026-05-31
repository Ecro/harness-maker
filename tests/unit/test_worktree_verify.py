"""Unit tests for the `worktree verify` anti-drift gate (review CR-1/CR-3, CC-3).

Real git ops inside tmp_path — mirrors test_worktree.py's repo fixture. The gate
must accept ONLY an existing linked worktree root and reject phantom paths, the
main checkout, non-git dirs, and subdirectories of a worktree.
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
    r = tmp_path / "repo"
    r.mkdir()
    _git(["init", "-b", "main"], cwd=r)
    _git(["config", "user.email", "test@example.com"], cwd=r)
    _git(["config", "user.name", "Test"], cwd=r)
    (r / "README.md").write_text("# repo\n")
    (r / ".gitignore").write_text(".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n")
    _git(["add", "."], cwd=r)
    _git(["commit", "-m", "init"], cwd=r)
    return r


def test_verify_accepts_linked_worktree(repo: Path) -> None:
    wt = worktree.create("execute", repo)[0]
    assert worktree.main(["verify", str(wt)]) == 0


def test_verify_rejects_main_repo_root(repo: Path) -> None:
    # CR-1: `git rev-parse --show-toplevel` from main returns main itself; the
    # gate must still reject it (drift onto main must not pass).
    assert worktree.main(["verify", str(repo)]) == 1


def test_verify_rejects_phantom_path(tmp_path: Path) -> None:
    phantom = tmp_path / "repo" / ".worktrees" / "execute-20260531T120000Z"
    assert worktree.main(["verify", str(phantom)]) == 1
    assert not phantom.exists()  # gate must not materialize it


def test_verify_rejects_non_git_dir(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert worktree.main(["verify", str(plain)]) == 1


def test_verify_rejects_subdir_of_worktree(repo: Path) -> None:
    wt = worktree.create("execute", repo)[0]
    sub = wt / "nested"
    sub.mkdir()
    assert worktree.main(["verify", str(sub)]) == 1


def test_verify_bad_arity_returns_2() -> None:
    assert worktree.main(["verify"]) == 2
    assert worktree.main(["verify", "a", "b"]) == 2
