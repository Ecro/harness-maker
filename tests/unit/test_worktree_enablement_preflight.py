"""Phase 6 (ADR-008): make-time enablement preflight.

`enablement_preflight(target)` returns `(should_flip, warning)` — flip the
`feature_branch_workflow` flag to True ONLY when the project has NO pending
old-model state (no unpopped `.hm-finalize-stash-*` ref, no live `.hm-loop-*`
marker, no in-flight `.worktrees/execute-*` worktree, no user-dirty base). It is
filesystem-only apart from the read-only `git status` the dirty-probe runs — the
migrate path never MUTATES git.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from harness_maker import worktree


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n.claude/\n")
    (repo / "README.md").write_text("x\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    (repo / ".claude").mkdir(exist_ok=True)
    return repo


# ── clean → flip ─────────────────────────────────────────────────────────────


def test_clean_project_flips(tmp_path: Path) -> None:
    repo = _clean_repo(tmp_path)
    should_flip, warning = worktree.enablement_preflight(repo)
    assert should_flip is True
    assert warning is None


# ── each pending state individually blocks + names itself ────────────────────


def test_pending_finalize_stash_blocks(tmp_path: Path) -> None:
    repo = _clean_repo(tmp_path)
    # a BARE finalize-stash ref (no live session marker) must still block — the
    # probe is marker-agnostic (validator C2).
    (repo / ".claude" / ".hm-finalize-stash-execute-deadbeef").write_text("ref\n")
    should_flip, warning = worktree.enablement_preflight(repo)
    assert should_flip is False
    assert warning is not None
    assert "finalize" in warning or "hm-finalize-stash" in warning


def test_live_loop_marker_blocks(tmp_path: Path) -> None:
    repo = _clean_repo(tmp_path)
    (repo / ".claude" / ".hm-loop-execute-abc123").write_text("x\n")
    should_flip, warning = worktree.enablement_preflight(repo)
    assert should_flip is False
    assert warning is not None
    assert "loop" in warning or "hm-loop" in warning


def test_in_flight_worktree_dir_blocks(tmp_path: Path) -> None:
    repo = _clean_repo(tmp_path)
    (repo / ".worktrees" / "execute-abc123-20260620T0000Z").mkdir(parents=True)
    should_flip, warning = worktree.enablement_preflight(repo)
    assert should_flip is False
    assert warning is not None
    assert "worktree" in warning


def test_in_flight_nonexecute_worktree_dir_blocks(tmp_path: Path) -> None:
    # REVIEW code P1: residue under a non-`execute` owned prefix (plan-/phase-/
    # autoloop-) must ALSO block — an `execute-*`-only glob would miss it.
    repo = _clean_repo(tmp_path)
    (repo / ".worktrees" / "autoloop-abc123-20260620T0000Z").mkdir(parents=True)
    should_flip, warning = worktree.enablement_preflight(repo)
    assert should_flip is False
    assert warning is not None
    assert "worktree" in warning


def test_user_dirty_base_blocks(tmp_path: Path) -> None:
    repo = _clean_repo(tmp_path)
    (repo / "user_edit.py").write_text("uncommitted user code\n")  # untracked user file
    should_flip, warning = worktree.enablement_preflight(repo)
    assert should_flip is False
    assert warning is not None
    assert "uncommitted" in warning or "dirty" in warning


def test_multiple_blockers_all_named(tmp_path: Path) -> None:
    repo = _clean_repo(tmp_path)
    (repo / ".claude" / ".hm-finalize-stash-execute-x").write_text("r\n")
    (repo / ".claude" / ".hm-loop-execute-y").write_text("x\n")
    should_flip, warning = worktree.enablement_preflight(repo)
    assert should_flip is False
    assert warning is not None
    assert "finalize" in warning
    assert "loop" in warning


def test_warning_mentions_remedy(tmp_path: Path) -> None:
    repo = _clean_repo(tmp_path)
    (repo / ".claude" / ".hm-loop-execute-z").write_text("x\n")
    _, warning = worktree.enablement_preflight(repo)
    assert warning is not None
    assert "re-run make" in warning  # actionable remedy


# ── no MUTATING git on the preflight (ADR-008) ───────────────────────────────


def test_preflight_runs_no_mutating_git(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repo = _clean_repo(tmp_path)
    seen: list[list[str]] = []
    real_run = subprocess.run

    def _spy(args, *a, **kw):  # type: ignore[no-untyped-def]
        if isinstance(args, list) and args and args[0] == "git":
            seen.append(args)
        return real_run(args, *a, **kw)

    monkeypatch.setattr(worktree.subprocess, "run", _spy)
    worktree.enablement_preflight(repo)
    mutating = {
        "commit",
        "branch",
        "worktree",
        "stash",
        "checkout",
        "reset",
        "merge",
        "rebase",
        "add",
        "push",
    }
    for call in seen:
        verb = call[1] if len(call) > 1 else ""
        assert verb not in mutating, f"preflight spawned a mutating git: {call}"


# ── sibling-repo strand sweep (REVIEW security P1) ───────────────────────────


def test_pending_sibling_stash_blocks(tmp_path: Path) -> None:
    # Clean PRIMARY but a sibling with a pending finalize stash must STILL block —
    # multi-repo strand gap: the loop marker lives only on the primary.
    repo = _clean_repo(tmp_path)
    sib = tmp_path / "sibling"
    (sib / ".claude").mkdir(parents=True)
    (sib / ".claude" / ".hm-finalize-stash-execute-s").write_text("ref\n")
    should_flip, warning = worktree.enablement_preflight(repo, sibling_bases=[sib])
    assert should_flip is False
    assert warning is not None
    assert "sibling" in warning


def test_clean_primary_and_sibling_flips(tmp_path: Path) -> None:
    repo = _clean_repo(tmp_path)
    sib = tmp_path / "sibling"
    (sib / ".claude").mkdir(parents=True)
    should_flip, warning = worktree.enablement_preflight(repo, sibling_bases=[sib])
    assert should_flip is True
    assert warning is None


# ── git-status failure is INDETERMINATE → defer (REVIEW security/Codex P2) ────


def test_git_status_failure_defers(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repo = _clean_repo(tmp_path)  # has a real .git
    real_run = worktree._run

    def _run_failing_status(args, *a, **kw):  # type: ignore[no-untyped-def]
        if isinstance(args, list) and args[:2] == ["git", "status"]:
            raise RuntimeError("git status timed out")
        return real_run(args, *a, **kw)

    monkeypatch.setattr(worktree, "_run", _run_failing_status)
    should_flip, warning = worktree.enablement_preflight(repo)
    assert should_flip is False
    assert warning is not None
    assert "could not verify" in warning
