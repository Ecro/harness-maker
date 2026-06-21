"""Fix 2 (PLAN-multisession-10-fleet-hardening ADR-002) — drift auto-refresh at
preflight + land drift-block.

- `task_preflight` auto-invokes `task_refresh` when the branch is clean + behind;
  diagnostics stay on stderr so the CLI's stdout remains exactly the `<WT>` path.
- `task_land` refuses a drifted (behind) branch unless `--allow-drift-land`, and
  the drift-block sits AFTER the already-landed convergence check so a partial-land
  re-run is never blocked by unrelated base drift (Codex P1).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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
    # Simulate the creating stage's process having exited (each /hm: stage is a
    # separate process): its registry row would be reclaimed, so a later preflight
    # with a fresh uuid does not see it as a foreign-LIVE holder.
    worktree.release_session(repo, session_uuid=f"u-{slug}")
    return wt


def _advance_base_disjoint(repo: Path, fname: str = "other.py") -> None:
    (repo / fname).write_text("base advance\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base advance"], repo)


# ── preflight auto-refresh ───────────────────────────────────────────────────


def test_preflight_auto_refreshes_clean_behind_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    _advance_base_disjoint(repo)
    assert worktree._branch_drift(repo, "hm/feat-x")[0] == 1  # behind before

    _wt, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="caller")
    assert any("auto-refreshed" in w for w in warnings)
    assert worktree._branch_drift(repo, "hm/feat-x")[0] == 0  # drift resolved


def test_preflight_cli_stdout_is_exactly_wt_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The auto-refresh's `[refresh]` diagnostics must NOT pollute stdout
    (Codex P2) — stdout stays exactly the `<WT>` path."""
    repo = _repo(tmp_path)
    wt = _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    _advance_base_disjoint(repo)

    rc = worktree.main(["task-preflight", "feat-x", str(repo)])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == str(wt)  # ONLY the path on stdout
    assert "[refresh]" in captured.err  # diagnostics went to stderr


def test_preflight_declines_refresh_on_conflict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    wt = _task_with_commit(repo, "feat-x", "clash.py", "task version\n")
    (repo / "clash.py").write_text("base version\n")  # add/add conflict on rebase
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base clash"], repo)

    rc = worktree.main(["task-preflight", "feat-x", str(repo)])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == str(wt)  # stdout still exactly the path
    assert "auto-refresh declined" in captured.err


# ── land drift-block ─────────────────────────────────────────────────────────


def test_land_blocks_drifted_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    _advance_base_disjoint(repo)  # branch now 1 behind
    rc = worktree.task_land(repo, "feat-x")
    assert rc == 1
    # branch + base untouched: the branch still exists
    assert worktree._branch_exists(repo, "hm/feat-x")


def test_land_allows_drifted_branch_with_flag(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    _advance_base_disjoint(repo)
    rc = worktree.task_land(repo, "feat-x", allow_drift_land=True)
    assert rc == 0
    # the task file landed on base
    assert (repo / "feature.py").exists()


def test_land_already_converged_not_blocked_by_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial-land re-run (already-converged branch) must reach the
    already-landed path BEFORE the drift-block (Codex P1) — unrelated base drift
    must not block it."""
    repo = _repo(tmp_path)
    _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    _advance_base_disjoint(repo)  # branch is behind

    # Force the convergence signal True → land must skip squash AND skip the
    # drift-block, proceeding to teardown rather than returning the drift rc1.
    monkeypatch.setattr(worktree, "_branch_content_in_head", lambda *a, **k: True)
    rc = worktree.task_land(repo, "feat-x")
    assert rc == 0  # converged → teardown, NOT the drift-block rc1


# ── task_refresh stdout contract ─────────────────────────────────────────────


def test_task_refresh_success_prints_to_stderr_not_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    _task_with_commit(repo, "feat-x", "feature.py", "task\n")
    _advance_base_disjoint(repo)
    rc = worktree.task_refresh(repo, "feat-x")
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""  # nothing on stdout
    assert "[refresh]" in captured.err
