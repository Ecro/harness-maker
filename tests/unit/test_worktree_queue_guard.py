"""Phase 1 — ADR-003 queue-guard.

PLAN-worktree-cross-session-data-loss-defense Phase 1: `worktree create`
ABORTs when ≥2 unpopped finalize stashes accumulate in `.claude/`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker.worktree import _count_pending_stashes


def _make_claude_dir(tmp_path: Path) -> Path:
    cd = tmp_path / ".claude"
    cd.mkdir()
    return cd


def _write_live_ref(claude_dir: Path, name: str, *, base: Path | None = None) -> None:
    marker = claude_dir / f".hm-loop-{name}"
    marker.write_text(f"{claude_dir.parent}\n", encoding="utf-8")
    ref = claude_dir / f".hm-finalize-stash-{name}"
    ref.write_text(
        "ref_sha: " + ("a" * 40) + "\n"
        f"base: {(base or claude_dir.parent).resolve()}\n"
        f"session_marker: {marker.resolve()}\n"
        "sibling_bases: \n"
        "session_uuid: deadbeef1234\n"
        "created_at: 2026-05-25T00:00:00+00:00\n",
        encoding="utf-8",
    )


# ── _count_pending_stashes helper ────────────────────────────────────────────


def test_count_pending_stashes_zero(tmp_path: Path) -> None:
    cd = _make_claude_dir(tmp_path)
    assert _count_pending_stashes(cd) == 0


def test_count_pending_stashes_one(tmp_path: Path) -> None:
    cd = _make_claude_dir(tmp_path)
    _write_live_ref(cd, "execute-A")
    assert _count_pending_stashes(cd) == 1


def test_count_pending_stashes_three(tmp_path: Path) -> None:
    cd = _make_claude_dir(tmp_path)
    for n in ("A", "B", "C"):
        _write_live_ref(cd, f"execute-{n}")
    assert _count_pending_stashes(cd) == 3


def test_count_pending_stashes_ignores_unrelated_files(tmp_path: Path) -> None:
    cd = _make_claude_dir(tmp_path)
    (cd / ".hm-loop-A").write_text("x")
    (cd / "harness.yaml").write_text("x")
    _write_live_ref(cd, "X")
    assert _count_pending_stashes(cd) == 1


def test_count_pending_stashes_ignores_invalid_or_stale_refs(tmp_path: Path) -> None:
    cd = _make_claude_dir(tmp_path)
    (cd / ".hm-finalize-stash-invalid").write_text("x")
    stale_marker = cd / ".hm-loop-execute-stale"
    (cd / ".hm-finalize-stash-execute-stale").write_text(
        "ref_sha: " + ("a" * 40) + "\n"
        f"base: {cd.parent.resolve()}\n"
        f"session_marker: {stale_marker.resolve()}\n"
        "sibling_bases: \n"
        "session_uuid: deadbeef1234\n"
        "created_at: 2026-05-25T00:00:00+00:00\n",
        encoding="utf-8",
    )
    assert _count_pending_stashes(cd) == 0


def test_count_pending_stashes_missing_dir(tmp_path: Path) -> None:
    assert _count_pending_stashes(tmp_path / "nope") == 0


# ── _cli_create queue-guard integration ─────────────────────────────────────


def _setup_git_repo_with_harness_yaml(tmp_path: Path) -> Path:
    """Init a real git repo with harness.yaml.worktree.scope = [execute]."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    # .claude/ + .worktrees/ gitignored mirrors real-world setup; otherwise
    # the dirty-base guard (Phase 2) would trip on untracked .claude/ files.
    (repo / ".gitignore").write_text(".claude/\n.worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    cd = repo / ".claude"
    cd.mkdir()
    (cd / "harness.yaml").write_text("worktree:\n  scope: [execute]\n", encoding="utf-8")
    return repo


def _run_cli_create(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "create", "execute", str(repo)],
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_cli_create_passes_with_zero_pending_stashes(tmp_path: Path) -> None:
    repo = _setup_git_repo_with_harness_yaml(tmp_path)
    proc = _run_cli_create(repo)
    assert proc.returncode == 0, f"unexpected fail: {proc.stderr}"
    # Output is the worktree path
    assert ".worktrees/execute-" in proc.stdout


def test_cli_create_passes_with_one_pending_stash(tmp_path: Path) -> None:
    repo = _setup_git_repo_with_harness_yaml(tmp_path)
    _write_live_ref(repo / ".claude", "execute-A", base=repo)
    proc = _run_cli_create(repo)
    assert proc.returncode == 0, f"unexpected fail: {proc.stderr}"


def test_cli_create_aborts_with_two_pending_stashes(tmp_path: Path) -> None:
    repo = _setup_git_repo_with_harness_yaml(tmp_path)
    _write_live_ref(repo / ".claude", "execute-A", base=repo)
    _write_live_ref(repo / ".claude", "execute-B", base=repo)
    proc = _run_cli_create(repo)
    assert proc.returncode != 0, f"expected ABORT, got success: {proc.stdout}"
    # Literal-substring contract for the wrapup-template LLM gate.
    assert (
        "≥2 unpopped finalize stashes" in proc.stderr
        or "2 unpopped finalize stashes" in proc.stderr
    )


def test_cli_create_aborts_with_three_pending_stashes(tmp_path: Path) -> None:
    repo = _setup_git_repo_with_harness_yaml(tmp_path)
    for n in ("A", "B", "C"):
        _write_live_ref(repo / ".claude", f"execute-{n}", base=repo)
    proc = _run_cli_create(repo)
    assert proc.returncode != 0


def test_cli_create_allow_stash_queue_bypasses_two_stashes(tmp_path: Path) -> None:
    """--allow-stash-queue escape hatch lets user proceed with N ≥ 2."""
    repo = _setup_git_repo_with_harness_yaml(tmp_path)
    _write_live_ref(repo / ".claude", "execute-A", base=repo)
    _write_live_ref(repo / ".claude", "execute-B", base=repo)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.worktree",
            "create",
            "execute",
            str(repo),
            "--allow-stash-queue",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"escape flag failed: {proc.stderr}"
    assert ".worktrees/execute-" in proc.stdout


def test_cli_create_abort_message_lists_pending_refs(tmp_path: Path) -> None:
    """Abort stderr names the pending ref files so user can /hm:wrapup them."""
    repo = _setup_git_repo_with_harness_yaml(tmp_path)
    _write_live_ref(repo / ".claude", "execute-A", base=repo)
    _write_live_ref(repo / ".claude", "execute-B", base=repo)
    proc = _run_cli_create(repo)
    assert proc.returncode != 0
    assert ".hm-finalize-stash-execute-A" in proc.stderr
    assert ".hm-finalize-stash-execute-B" in proc.stderr


def test_cli_create_abort_message_suggests_wrapup(tmp_path: Path) -> None:
    """Abort stderr suggests /hm:wrapup as the remediation path."""
    repo = _setup_git_repo_with_harness_yaml(tmp_path)
    _write_live_ref(repo / ".claude", "execute-A", base=repo)
    _write_live_ref(repo / ".claude", "execute-B", base=repo)
    proc = _run_cli_create(repo)
    assert "/hm:wrapup" in proc.stderr or "wrapup" in proc.stderr.lower()


@pytest.mark.skip(
    reason="pytest.skip placeholder — when ADR-004 Session UUID lands (Phase 3), "
    "queue-guard should ONLY count refs whose session_uuid != current uuid "
    "(own-session pending refs from a prior interrupted run are safe to clear)."
)
def test_cli_create_ignores_own_session_stashes_after_phase_3() -> None:
    pass
