"""Phase 5 (ADR-002/004/006): flag-on stage preflight helper.

`task_preflight(base, slug, session_uuid=...)` idempotently ensures the
persistent `.worktrees/<slug>/` task worktree (Phase 2), reclaims dead registry
rows (Phase 1), and returns `(wt_path, warnings)` where warnings surface other
active sessions + a drift notice when the task branch fell behind the base tip.
The `task-preflight` CLI subcommand prints the WT path to stdout (for `<WT>`
capture) and warnings to stderr.
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


def _branches(repo: Path) -> list[str]:
    return _git(["branch", "--format=%(refname:short)"], repo).split()


# ── creation + idempotency ───────────────────────────────────────────────────


def test_preflight_creates_and_returns_task_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    assert wt == worktree.task_worktree_path(repo, "feat-x")
    assert wt.is_dir()
    assert worktree._current_branch(wt) == "hm/feat-x"
    rows = worktree._read_sessions(repo)
    assert any(r.branch == "hm/feat-x" and r.session_uuid == "u-1" for r in rows)
    # fresh task off the base tip → no drift warning
    assert not any("behind" in w for w in warnings)


def test_preflight_idempotent_reuse(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt1, _ = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    wt2, _ = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    assert wt1 == wt2
    assert _branches(repo).count("hm/feat-x") == 1
    rows = worktree._read_sessions(repo)
    assert len([r for r in rows if r.branch == "hm/feat-x"]) == 1


# ── active-session surface ───────────────────────────────────────────────────


def test_preflight_surfaces_foreign_active_session(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    # a different live session already holds another task
    worktree.task_create(repo, "other-task", session_uuid="u-foreign")
    _, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-mine")
    surfaced = " ".join(warnings)
    assert "other-task" in surfaced
    assert "u-mine" not in surfaced  # never lists our own session


def test_preflight_no_foreign_warning_when_alone(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    assert not any("active session" in w for w in warnings)


def test_preflight_surfaces_concurrent_same_slug_session(tmp_path: Path) -> None:
    # REVIEW Codex P2: a SECOND session entering the SAME task must be warned,
    # even though task_create replaces the same-branch registry row.
    repo = _repo(tmp_path)
    worktree.task_create(repo, "feat-x", session_uuid="u-first")
    _, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-second")
    collision = [w for w in warnings if "already hold task" in w]
    assert collision, f"expected a same-slug collision warning, got {warnings!r}"
    assert "feat-x" in collision[0]


def test_preflight_idempotent_reuse_no_self_collision(tmp_path: Path) -> None:
    # Same uuid re-entering its own task must NOT self-report as a collision.
    repo = _repo(tmp_path)
    worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    _, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    assert not any("already hold task" in w for w in warnings)


# ── drift detection ──────────────────────────────────────────────────────────


def test_branch_drift_counts_behind_and_ahead(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = worktree.task_create(repo, "feat-x", session_uuid="u-1")
    # one commit ahead on the task branch
    (wt / "feature.py").write_text("task\n")
    _git(["add", "-A"], wt)
    _git(["commit", "-m", "wip(execute): feat-x"], wt)
    # advance the base by two commits → branch is 2 behind
    (repo / "a.txt").write_text("a\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base 1"], repo)
    (repo / "b.txt").write_text("b\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base 2"], repo)
    behind, ahead = worktree._branch_drift(repo, "hm/feat-x")
    assert behind == 2
    assert ahead == 1


def test_preflight_drift_warning_points_at_task_refresh(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    worktree.task_create(repo, "feat-x", session_uuid="u-1")
    (repo / "a.txt").write_text("a\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base advance"], repo)
    _, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    drift = [w for w in warnings if "behind" in w]
    assert drift, f"expected a drift warning, got {warnings!r}"
    assert "task-refresh" in drift[0]


# ── CLI dispatch wiring (Phase-4 dead-entry-point lesson) ─────────────────────


def test_preflight_cli_dispatch_is_wired(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    rc = worktree.main(["task-preflight", "feat-x", str(repo)])
    assert rc == 0
    assert worktree.task_worktree_path(repo, "feat-x").is_dir()


def test_preflight_cli_usage_on_missing_slug(tmp_path: Path) -> None:
    rc = worktree.main(["task-preflight"])
    assert rc == 2
