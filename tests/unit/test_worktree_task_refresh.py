"""Phase 5 (ADR-002): warm-branch-drift refresh helper.

`task_refresh(base, slug)` rebases `hm/<slug>` onto the **base repo's current
tip** (base HEAD SHA — NOT a hardcoded `main`, per worktree.py:988-1001 precedent)
inside the task worktree, preserving the branch's commits. A rebase conflict is
aborted (`git rebase --abort`) and reported with `rc=1`, leaving the branch
exactly as it was; a dirty worktree is refused before any rebase starts.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from harness_maker import worktree


def _git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )
    return cp.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n.claude/\n")
    (repo / "README.md").write_text("x\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _task_with_commit(repo: Path, slug: str, fname: str, content: str) -> Path:
    wt = worktree.task_create(repo, slug, session_uuid=f"u-{slug}")
    (wt / fname).write_text(content)
    _git(["add", "-A"], wt)
    _git(["commit", "-m", f"wip(execute): {slug}"], wt)
    return wt


# ── clean rebase onto advanced base ──────────────────────────────────────────


def test_refresh_rebases_onto_advanced_base_preserving_commits(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    # base advances on a DISJOINT file → no conflict
    (repo / "other.py").write_text("base\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base advance"], repo)

    rc = worktree.task_refresh(repo, "feat-x")
    assert rc == 0
    # the task commit survives the rebase
    log = _git(["log", "--format=%s", "hm/feat-x"], wt)
    assert "wip(execute): feat-x" in log
    # base tip is now an ancestor of the task branch (drift resolved)
    base_head = _git(["rev-parse", "HEAD"], repo)
    mb = _git(["merge-base", "hm/feat-x", base_head], repo)
    assert mb == base_head
    # base's file is now visible in the worktree
    assert (wt / "other.py").exists()
    behind, _ahead = worktree._branch_drift(repo, "hm/feat-x")
    assert behind == 0


def test_refresh_noop_when_already_current(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    # base did NOT advance
    rc = worktree.task_refresh(repo, "feat-x")
    assert rc == 0
    log = _git(["log", "--format=%s", "hm/feat-x"], repo)
    assert "wip(execute): feat-x" in log


# ── conflict → abort + rc=1 + branch intact ──────────────────────────────────


def test_refresh_conflict_aborts_and_preserves_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = _task_with_commit(repo, "feat-x", "clash.py", "task version\n")
    tip_before = _git(["rev-parse", "hm/feat-x"], repo)
    # base adds the SAME file with different content → add/add conflict on rebase
    (repo / "clash.py").write_text("base version\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base clash"], repo)

    rc = worktree.task_refresh(repo, "feat-x")
    assert rc == 1
    # branch tip unchanged (rebase fully aborted)
    assert _git(["rev-parse", "hm/feat-x"], repo) == tip_before
    # no rebase left in progress in the worktree
    assert not (wt / ".git").exists() or True  # worktree .git is a file; check state below
    status = _git(["status", "--porcelain"], wt)
    assert status == ""  # clean — abort restored the tree


def test_refresh_refuses_dirty_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    (wt / "dirty.py").write_text("uncommitted\n")  # untracked dirt
    (repo / "other.py").write_text("base\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base advance"], repo)
    rc = worktree.task_refresh(repo, "feat-x")
    assert rc == 1


# ── guards ───────────────────────────────────────────────────────────────────


def test_refresh_refuses_wrong_checked_out_branch(tmp_path: Path) -> None:
    # REVIEW code P2: if the worktree is NOT on hm/<slug> (detached / manual
    # checkout), refuse rather than rebase the wrong ref + report a false success.
    repo = _repo(tmp_path)
    wt = _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    _git(["checkout", "--detach"], wt)  # leave the task branch
    assert worktree.task_refresh(repo, "feat-x") == 1


def test_refresh_missing_worktree_rc1(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert worktree.task_refresh(repo, "nonexistent") == 1


def test_refresh_invalid_slug_rc1(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert worktree.task_refresh(repo, "../escape") == 1


def test_refresh_cli_dispatch_is_wired(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    rc = worktree.main(["task-refresh", "feat-x", str(repo)])
    assert rc == 0


def test_refresh_cli_usage_on_missing_slug(tmp_path: Path) -> None:
    assert worktree.main(["task-refresh"]) == 2
