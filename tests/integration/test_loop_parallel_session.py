"""P6 — end-to-end parallel-session safety for /hm:loop (loop-marker-session-scoping).

Two concurrent sessions share ONE base repo. Drives the REAL CLI/hook boundaries
(subprocess: `worktree create --claude-session-id`, `worktree loop-mode-active`,
`loop_gate --mode stop-hook` over stdin JSON) — the integration seam unit tests
can't reach (CLAUDE.md §8). Proves: markers coexist; the Stop-hook blocks only the
owning session; loop-mode detection is session-scoped; one session's cleanup leaves
the other's marker intact.

Opt-in via HM_RUN_PARALLEL_SESSION=1 (mirrors test_worktree_parallel_session.py).
Runs inside tmp_path with `git init` — never touches the real repo.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker.loop_marker import parse_marker_session_id

pytestmark = pytest.mark.skipif(
    os.getenv("HM_RUN_PARALLEL_SESSION") != "1",
    reason="opt-in via HM_RUN_PARALLEL_SESSION=1 (real-FS multi-session integration).",
)

SESSION_A = "0a1b2c3d-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SESSION_B = "0b1b2c3d-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
SESSION_C = "0c1b2c3d-cccc-4ccc-8ccc-cccccccccccc"  # idle, never starts a loop


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True, timeout=15
    )


def _init_base_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "base-repo"
    repo.mkdir()
    _git("init", "-b", "main", ".", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    # The CLI `worktree create` engages isolation only when harness.yaml's
    # worktree.scope includes the stage (_scope_includes); without it the CLI
    # takes the no-isolation empty path and writes no marker.
    claude = repo / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text("worktree:\n  scope: [execute]\n", encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "init", cwd=repo)
    return repo


def _create_loop(repo: Path, session_id: str) -> None:
    """Simulate a session's /hm:loop `worktree create` (passes --claude-session-id)."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.worktree",
            "create",
            "execute",
            str(repo),
            "--claude-session-id",
            session_id,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _stop_hook(repo: Path, session_id: str) -> int:
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "cwd": str(repo),
            "workspace": {"current_dir": str(repo)},
            "session_id": session_id,
        }
    )
    cp = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.loop_gate", "--mode", "stop-hook"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return cp.returncode


def _loop_mode_active(repo: Path, session_id: str) -> int:
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.worktree",
            "loop-mode-active",
            str(repo),
            "--claude-session-id",
            session_id,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return cp.returncode


def _markers(repo: Path) -> list[Path]:
    return sorted((repo / ".claude").glob(".hm-loop-*"))


def test_two_session_markers_coexist(tmp_path: Path) -> None:
    repo = _init_base_repo(tmp_path)
    _create_loop(repo, SESSION_A)
    _create_loop(repo, SESSION_B)
    sids = {parse_marker_session_id(m.read_text(encoding="utf-8")) for m in _markers(repo)}
    assert SESSION_A in sids
    assert SESSION_B in sids


def test_stop_hook_blocks_only_owning_session(tmp_path: Path) -> None:
    repo = _init_base_repo(tmp_path)
    _create_loop(repo, SESSION_A)
    _create_loop(repo, SESSION_B)
    assert _stop_hook(repo, SESSION_A) == 2  # A's loop active → blocked
    assert _stop_hook(repo, SESSION_B) == 2  # B's loop active → blocked
    assert _stop_hook(repo, SESSION_C) == 0  # idle peer → never blocked


def test_loop_mode_detection_is_session_scoped(tmp_path: Path) -> None:
    repo = _init_base_repo(tmp_path)
    _create_loop(repo, SESSION_A)
    assert _loop_mode_active(repo, SESSION_A) == 0  # A's stage → loop-mode
    assert _loop_mode_active(repo, SESSION_C) == 1  # C's standalone /hm:plan → NOT loop-mode


def test_finalize_one_session_leaves_the_other_marker(tmp_path: Path) -> None:
    repo = _init_base_repo(tmp_path)
    _create_loop(repo, SESSION_A)
    _create_loop(repo, SESSION_B)
    # Identify A's worktree marker, finalize it, assert B's survives.
    before = _markers(repo)
    a_marker = next(
        m for m in before if parse_marker_session_id(m.read_text(encoding="utf-8")) == SESSION_A
    )
    a_wt = Path(
        next(ln for ln in a_marker.read_text(encoding="utf-8").splitlines() if ln.startswith("/"))
    )
    # stage-only is the success/loop-close path that clears the OWN marker.
    subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "finalize", str(a_wt), "stage-only"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    after_sids = {parse_marker_session_id(m.read_text(encoding="utf-8")) for m in _markers(repo)}
    assert SESSION_B in after_sids  # B untouched by A's finalize
    assert SESSION_A not in after_sids  # A's own marker cleared
    assert _stop_hook(repo, SESSION_B) == 2  # B still guarded
