"""Phase 5 — ADR-006 finalize scope-guard.

`_verify_scope_subset(base, wt_branch, staged_before)` ensures the merge
introduced only paths from the worktree's own diff. Detects the
'finalize-pulls-orphan-wip-into-main' contamination class even when
ADR-002/003 escape flags are in use.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from harness_maker.worktree import _verify_scope_subset


def _git(args: list[str], cwd: Path) -> str:
    p = subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)
    return p.stdout


def _make_repo_with_wt_branch(tmp_path: Path) -> tuple[Path, str]:
    """Create repo + a wt branch with one extra commit touching wt-only.txt.
    Returns (repo_path, wt_branch_name)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "t@e.com"], cwd=repo)
    _git(["config", "user.name", "T"], cwd=repo)
    (repo / "README.md").write_text("x")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-m", "init"], cwd=repo)
    # Create wt branch + commit a wt-only change
    _git(["checkout", "-b", "execute-wt-test"], cwd=repo)
    (repo / "wt-only.txt").write_text("wt feature")
    _git(["add", "wt-only.txt"], cwd=repo)
    _git(["commit", "-m", "feature on wt"], cwd=repo)
    _git(["checkout", "main"], cwd=repo)
    return repo, "execute-wt-test"


# ── happy path: only wt-diff in staged ─────────────────────────────────────


def test_scope_subset_clean_when_only_wt_diff_staged(tmp_path: Path) -> None:
    repo, wt_branch = _make_repo_with_wt_branch(tmp_path)
    staged_before: set[str] = set()
    _git(["merge", "--squash", wt_branch], cwd=repo)
    # The merge staged wt-only.txt (per wt branch's diff)
    ok, contamination = _verify_scope_subset(repo, wt_branch, staged_before)
    assert ok is True
    assert contamination == set()


# ── contamination path: extra staged file outside wt diff ──────────────────


def test_scope_subset_detects_contamination_extra_staged(tmp_path: Path) -> None:
    repo, wt_branch = _make_repo_with_wt_branch(tmp_path)
    staged_before: set[str] = set()
    _git(["merge", "--squash", wt_branch], cwd=repo)
    # Add an unrelated staged file (simulating contamination from elsewhere)
    (repo / "contamination.txt").write_text("not from wt")
    _git(["add", "contamination.txt"], cwd=repo)
    ok, contamination = _verify_scope_subset(repo, wt_branch, staged_before)
    assert ok is False
    assert "contamination.txt" in contamination


# ── --allow-dirty-base interaction: pre-existing staged content excluded ────


def test_scope_subset_excludes_staged_before(tmp_path: Path) -> None:
    """When --allow-dirty-base was used at create-time, pre-existing staged
    content should NOT count as contamination — only the merge-introduced
    delta matters."""
    repo, wt_branch = _make_repo_with_wt_branch(tmp_path)
    # Pre-existing staged content (user had it staged before finalize)
    (repo / "user-staged.txt").write_text("user already had this")
    _git(["add", "user-staged.txt"], cwd=repo)
    staged_before = set(_git(["diff", "--cached", "--name-only"], cwd=repo).strip().splitlines())
    assert "user-staged.txt" in staged_before
    _git(["merge", "--squash", wt_branch], cwd=repo)
    # Now staged_after includes user-staged.txt + wt-only.txt
    # But the DELTA (staged_after - staged_before) = wt-only.txt only.
    ok, contamination = _verify_scope_subset(repo, wt_branch, staged_before)
    assert ok is True, f"unexpected contamination: {contamination}"


def test_scope_subset_detects_contamination_even_with_staged_before(tmp_path: Path) -> None:
    """Pre-existing staged user content is fine, but NEW staged paths outside
    wt diff still fire the guard."""
    repo, wt_branch = _make_repo_with_wt_branch(tmp_path)
    (repo / "user-staged.txt").write_text("user")
    _git(["add", "user-staged.txt"], cwd=repo)
    staged_before = set(_git(["diff", "--cached", "--name-only"], cwd=repo).strip().splitlines())
    _git(["merge", "--squash", wt_branch], cwd=repo)
    # New contamination AFTER merge
    (repo / "contamination.txt").write_text("not from wt")
    _git(["add", "contamination.txt"], cwd=repo)
    ok, contamination = _verify_scope_subset(repo, wt_branch, staged_before)
    assert ok is False
    assert "contamination.txt" in contamination
    # user-staged.txt is in staged_before → not in delta → not in contamination
    assert "user-staged.txt" not in contamination
