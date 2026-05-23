"""Phase 2 — ADR-002 dirty-base guard.

`worktree create` ABORTs when base repo has uncommitted USER changes (filtered
by `_is_harness_artifact`); `--allow-dirty-base` bypasses. Harness-artifact
dirt (.claude/.hm-loop-*, .claude/.hm-finalize-stash-*, .worktrees/) does
NOT trip the guard — those are owned by the harness itself.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from harness_maker.worktree import _has_user_dirty_state


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    # Mirror real-world: .claude/ is gitignored so it does not pollute
    # `git status --porcelain` and trip the dirty-base guard on untracked
    # config files.
    (repo / ".gitignore").write_text(".claude/\n.worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    cd = repo / ".claude"
    cd.mkdir()
    (cd / "harness.yaml").write_text("worktree:\n  scope: [execute]\n", encoding="utf-8")
    return repo


# ── _has_user_dirty_state helper ────────────────────────────────────────────


def test_has_user_dirty_state_clean(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    assert _has_user_dirty_state(repo) is False


def test_has_user_dirty_state_user_dirty_file(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "user-edit.txt").write_text("user content")
    assert _has_user_dirty_state(repo) is True


def test_has_user_dirty_state_modified_file(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("modified")
    assert _has_user_dirty_state(repo) is True


def test_has_user_dirty_state_harness_artifact_only_clean(tmp_path: Path) -> None:
    """Harness-owned dirt (.claude/.hm-loop-*, .worktrees/) does NOT count."""
    repo = _init_repo(tmp_path)
    (repo / ".claude" / ".hm-loop-test").write_text("x")
    (repo / ".claude" / ".hm-finalize-stash-test").write_text("x")
    assert _has_user_dirty_state(repo) is False


def test_has_user_dirty_state_mixed_user_plus_harness(tmp_path: Path) -> None:
    """User dirt mixed with harness dirt → still True."""
    repo = _init_repo(tmp_path)
    (repo / ".claude" / ".hm-loop-test").write_text("x")
    (repo / "user-edit.txt").write_text("user")
    assert _has_user_dirty_state(repo) is True


# ── _cli_create dirty-base integration ──────────────────────────────────────


def _run_create(repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "create", "execute", str(repo), *extra],
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_cli_create_passes_when_base_clean(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    proc = _run_create(repo)
    assert proc.returncode == 0, proc.stderr


def test_cli_create_aborts_when_user_dirty(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "user-edit.txt").write_text("user")
    proc = _run_create(repo)
    assert proc.returncode != 0, f"expected ABORT, got success: {proc.stdout}"
    assert "dirty" in proc.stderr.lower() or "uncommitted" in proc.stderr.lower()


def test_cli_create_lists_dirty_files_in_abort_message(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "user-edit.txt").write_text("user")
    proc = _run_create(repo)
    assert proc.returncode != 0
    assert "user-edit.txt" in proc.stderr


def test_cli_create_allow_dirty_base_bypasses(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "user-edit.txt").write_text("user")
    proc = _run_create(repo, "--allow-dirty-base")
    assert proc.returncode == 0, f"escape flag failed: {proc.stderr}"
    assert ".worktrees/execute-" in proc.stdout


def test_cli_create_harness_artifact_dirt_does_not_trip_guard(tmp_path: Path) -> None:
    """REVIEW round 3 invariant — .hm-loop-* and .hm-finalize-stash-* are
    harness-owned, not user-owned. They MUST NOT trigger the dirty-base abort."""
    repo = _init_repo(tmp_path)
    (repo / ".claude" / ".hm-loop-prior-session").write_text("x")
    # Note: cannot test .hm-finalize-stash-* because Phase 1 queue-guard would
    # fire if we had ≥2. One is fine.
    (repo / ".claude" / ".hm-finalize-stash-execute-X").write_text("x")
    proc = _run_create(repo)
    assert proc.returncode == 0, f"harness dirt tripped guard: {proc.stderr}"
