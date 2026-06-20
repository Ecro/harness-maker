"""Phase 3 (ADR-007): commit-not-stash finalize for the feature-branch model.

When `worktree.feature_branch_workflow: true`, `finalize success|stage-only`
captures pending work as a WIP commit on the task branch `hm/<slug>` and does
NOT touch the base working tree: no `git stash`, no merge-to-base, no
`.hm-finalize-stash-*` ref file, no worktree teardown (the persistent worktree
survives until the Phase-4 squash-land). The OLD deferred-stash path stays
intact and is exercised with the flag OFF (dual-path invariant).
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


def _repo(tmp_path: Path, *, flag: bool) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n.claude/\n.env\n")
    (repo / "README.md").write_text("x\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    claude = repo / ".claude"
    claude.mkdir(exist_ok=True)
    flag_val = "true" if flag else "false"
    (claude / "harness.yaml").write_text(f"worktree:\n  feature_branch_workflow: {flag_val}\n")
    return repo


def _stash_refs(repo: Path) -> list[Path]:
    return sorted((repo / ".claude").glob(".hm-finalize-stash-*"))


def _dirty_the_worktree(wt: Path) -> None:
    (wt / "feature.py").write_text("print('work')\n")


# ── flag ON: commit-not-stash ────────────────────────────────────────────────


def test_flag_on_stage_only_commits_on_branch_no_stash(tmp_path: Path) -> None:
    repo = _repo(tmp_path, flag=True)
    base_head = _git(["rev-parse", "HEAD"], repo)
    wt = worktree.task_create(repo, "feat", session_uuid="u-1")
    _dirty_the_worktree(wt)

    rc = worktree._cli_finalize([str(wt), "stage-only"])

    assert rc == 0
    # worktree persists (NOT torn down — land owns teardown)
    assert wt.is_dir()
    # a WIP commit landed on the task branch
    log = _git(["log", "--oneline", "hm/feat"], repo)
    assert "wip" in log.lower()
    assert (wt / "feature.py").exists()
    # base HEAD unchanged — no merge-to-base happened
    assert _git(["rev-parse", "HEAD"], repo) == base_head
    # exit criterion: zero finalize-stash ref files
    assert _stash_refs(repo) == []


def test_flag_on_success_no_squash_to_base_no_stash(tmp_path: Path) -> None:
    repo = _repo(tmp_path, flag=True)
    base_head = _git(["rev-parse", "HEAD"], repo)
    wt = worktree.task_create(repo, "feat", session_uuid="u-1")
    _dirty_the_worktree(wt)

    rc = worktree._cli_finalize([str(wt), "success"])

    assert rc == 0
    assert wt.is_dir()  # persistent — success finalize does NOT land (Phase 4 does)
    assert _git(["rev-parse", "HEAD"], repo) == base_head
    assert _stash_refs(repo) == []


def test_flag_on_clean_worktree_is_noop(tmp_path: Path) -> None:
    repo = _repo(tmp_path, flag=True)
    wt = worktree.task_create(repo, "feat", session_uuid="u-1")
    # no dirt
    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0
    assert wt.is_dir()
    assert _stash_refs(repo) == []


def test_flag_on_non_contact_leaves_base_dirt_untouched(tmp_path: Path) -> None:
    """ADR-007 non-contact: a pre-existing dirty user file on base is never
    stashed or modified by the new-path finalize."""
    repo = _repo(tmp_path, flag=True)
    (repo / "README.md").write_text("user local edit\n")  # base dirt
    wt = worktree.task_create(repo, "feat", session_uuid="u-1")
    _dirty_the_worktree(wt)

    rc = worktree._cli_finalize([str(wt), "stage-only"])

    assert rc == 0
    # base dirt preserved verbatim
    assert (repo / "README.md").read_text() == "user local edit\n"
    # no git stash entry created on base
    assert _git(["stash", "list"], repo) == ""
    assert _stash_refs(repo) == []


def test_flag_on_wip_commit_reachable_on_branch(tmp_path: Path) -> None:
    """Durability: the captured work is a reachable commit on hm/<slug>."""
    repo = _repo(tmp_path, flag=True)
    wt = worktree.task_create(repo, "feat", session_uuid="u-1")
    _dirty_the_worktree(wt)
    worktree._cli_finalize([str(wt), "stage-only"])
    # the file is committed on the branch (reachable from the tip)
    tree = _git(["ls-tree", "-r", "--name-only", "hm/feat"], repo)
    assert "feature.py" in tree.split()


def test_flag_on_idempotent_rerun(tmp_path: Path) -> None:
    repo = _repo(tmp_path, flag=True)
    wt = worktree.task_create(repo, "feat", session_uuid="u-1")
    _dirty_the_worktree(wt)
    assert worktree._cli_finalize([str(wt), "stage-only"]) == 0
    # second run: worktree now clean → no-op
    assert worktree._cli_finalize([str(wt), "stage-only"]) == 0
    assert wt.is_dir()
    assert _stash_refs(repo) == []


def test_flag_on_residual_dirty_after_capture_fails_loudly(
    tmp_path: Path, monkeypatch: object
) -> None:
    """REVIEW iter-3 (Codex P1 + code-reviewer P2): if a concurrent writer leaves
    the worktree dirty after capture, finalize must NOT report success — a later
    land could otherwise trust rc=0 and tear down over uncommitted work."""
    repo = _repo(tmp_path, flag=True)
    wt = worktree.task_create(repo, "feat", session_uuid="u-1")

    def _racey_capture(w: Path) -> bool:
        # Simulate a writer dirtying the tree around/after the capture commit.
        (w / "raced.py").write_text("late write\n")
        return True

    monkeypatch.setattr(worktree, "_capture_pending_in_worktree", _racey_capture)  # type: ignore[attr-defined]

    rc = worktree._cli_finalize([str(wt), "stage-only"])

    assert rc == 1  # residual dirt → loud failure, never a false success
    assert wt.is_dir()  # preserved for recovery (no teardown)
    assert _stash_refs(repo) == []


def test_flag_on_fail_preserves_persistent_worktree(tmp_path: Path) -> None:
    """Validator critical: a blocked stage must NOT destroy the persistent task
    worktree. Under the flag, finalize fail captures the WIP on the branch and
    leaves the worktree + registry row intact (teardown is Phase-4 land only)."""
    repo = _repo(tmp_path, flag=True)
    wt = worktree.task_create(repo, "feat", session_uuid="u-1")
    _dirty_the_worktree(wt)

    rc = worktree._cli_finalize([str(wt), "fail"])

    assert rc == 0
    assert wt.is_dir()  # persistent worktree survives the blocker
    assert "hm/feat" in _git(["branch", "--format=%(refname:short)"], repo).split()
    # registry row stays — the task is still claimed (blocked, not landed)
    assert [r.branch for r in worktree._read_sessions(repo)] == ["hm/feat"]
    assert _stash_refs(repo) == []


def test_flag_on_legacy_worktree_uses_old_path(tmp_path: Path) -> None:
    """Absent-case (validator W4): a legacy disposable `execute-<uuid>` worktree
    finalized while the flag is ON must still take the OLD stash+merge+clean
    path — identity is the `hm/` branch prefix, not just the global flag."""
    repo = _repo(tmp_path, flag=True)
    wt = worktree.create("execute", repo)[0]  # legacy: branch == dir, no hm/ prefix
    _dirty_the_worktree(wt)

    rc = worktree._cli_finalize([str(wt), "stage-only"])

    assert rc == 0
    # routed to the OLD path despite flag ON → worktree torn down + merged to base
    assert not wt.is_dir()
    staged = _git(["diff", "--cached", "--name-only"], repo)
    assert "feature.py" in staged.split()


# ── flag OFF: OLD deferred-stash path still runs (dual-path invariant) ─────────


def test_flag_off_old_path_merges_and_cleans_up(tmp_path: Path) -> None:
    """With the flag OFF, finalize stage-only runs the legacy path on a genuine
    legacy `execute-<uuid>` worktree (dir name == branch name): it captures the
    WIP, merges the branch onto base, and tears the worktree down."""
    repo = _repo(tmp_path, flag=False)
    wt = worktree.create("execute", repo)[0]  # legacy worktree (dir==branch)
    _dirty_the_worktree(wt)

    rc = worktree._cli_finalize([str(wt), "stage-only"])

    assert rc == 0
    # OLD path cleans up the worktree (force-removed) — the discriminator vs new path
    assert not wt.is_dir()
    # the change is staged onto the base branch (merge --no-commit)
    staged = _git(["diff", "--cached", "--name-only"], repo)
    assert "feature.py" in staged.split()
