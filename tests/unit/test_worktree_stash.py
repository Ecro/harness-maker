"""Stash isolation envelope around finalize (PLAN-worktree-finalize-stash-isolation).

Phase 1 scope (this file's first test): success mode + dirty base happy path.
Phase 2/4 will append tests for handshake, classified failures, multi-repo,
and submodule abort.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker import worktree


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed args, no shell
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repo with one commit on `main`, .gitignore pre-tracked.

    The pre-tracked .gitignore mirrors a real project that already excludes
    the harness's per-session markers and stash-ref files. Without it,
    ``worktree.create()`` auto-writes a fresh .gitignore which then appears
    untracked in ``git status --porcelain`` and gets pulled into the stash —
    the test would then see a non-empty stash even on a "clean" base.
    """
    r = tmp_path / "repo"
    r.mkdir()
    _git(["init", "-b", "main"], cwd=r)
    _git(["config", "user.email", "test@example.com"], cwd=r)
    _git(["config", "user.name", "Test"], cwd=r)
    (r / "README.md").write_text("# repo\n")
    (r / ".gitignore").write_text(
        ".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n"
    )
    _git(["add", "README.md", ".gitignore"], cwd=r)
    _git(["commit", "-m", "init"], cwd=r)
    return r


def _porcelain(repo: Path) -> str:
    return _git(["status", "--porcelain"], cwd=repo).stdout


def test_success_dirty_base_happy_path(repo: Path) -> None:
    """ADR-001 success mode: dirty base is stashed → squash committed → stash popped (unstaged).

    Reproduces the original user incident: a worktree's commits get squashed back
    into main while main holds unrelated dirty work. With the stash envelope, the
    user's dirty work survives intact (modulo staging collapse per ADR-001 §3).
    """
    # 1. Create the worktree + a commit on its branch (the "scope").
    (wt,) = worktree.create("execute", repo)
    feature = wt / "feature.py"
    feature.write_text("def feature() -> None:\n    pass\n")
    _git(["add", "feature.py"], cwd=wt)
    _git(["commit", "-m", "add feature"], cwd=wt)

    # 2. On base, modify a tracked file AND stage it — this is the cross-session WIP
    #    that the squash must NOT contaminate. Staged is the "bug class" the PLAN targets
    #    (unstaged-only would survive via current code; staged is what wrapup commits sweep).
    original = (repo / "README.md").read_text()
    wip_content = original + "\nUSER WIP (do not lose this)\n"
    (repo / "README.md").write_text(wip_content)
    _git(["add", "README.md"], cwd=repo)
    pre_status = _porcelain(repo)
    assert "M  README.md" in pre_status, (
        f"setup precondition: README must be staged before finalize. status: {pre_status!r}"
    )

    # 3. Run finalize success — this should wrap squash in stash isolation.
    rc = worktree._cli_finalize([str(wt), "success"])
    assert rc == 0, "finalize success should return 0 on the happy path"

    # 4. Base HEAD now contains the squash result.
    log_files = _git(["log", "-1", "--name-only", "--format="], cwd=repo).stdout
    assert "feature.py" in log_files, (
        f"squash should have committed feature.py to base HEAD. files in HEAD: {log_files!r}"
    )

    # 5. Base README content is restored to the WIP version (transparent stash).
    assert (repo / "README.md").read_text() == wip_content, (
        "user's WIP content must be restored after stash pop"
    )

    # 6. README is restored as UNSTAGED (per ADR-001 §3 — staging collapse trade-off).
    post_status = _porcelain(repo)
    assert " M README.md" in post_status, (
        f"README should be unstaged-modified after pop (staging collapse). status: {post_status!r}"
    )
    # Belt + braces: it should NOT be in the staged column anymore.
    assert "M  README.md" not in post_status, (
        f"README must not remain staged after pop. status: {post_status!r}"
    )

    # 7. The squash commit itself must contain ONLY feature.py — README must NOT be in HEAD.
    assert "README.md" not in log_files, (
        f"README.md must NOT appear in the squash commit (no contamination). files: {log_files!r}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2: stage-only handshake (.hm-finalize-stash-{wt_name} ref file +
# post-commit-pop CLI). ADR-001 §2.
# ──────────────────────────────────────────────────────────────────────────────


def test_stage_only_writes_ref_file_when_dirty(repo: Path) -> None:
    """Stage-only with dirty base writes ref file; does NOT pop in finalize.

    The pop is deferred to post-commit-pop (invoked by wrapup after its commit).
    Until then, the user's dirty work lives in the stash, ref file points to it,
    and the squash result is staged on base waiting for wrapup.
    """
    (wt,) = worktree.create("execute", repo)
    (wt / "feature.py").write_text("def feature() -> None:\n    pass\n")
    _git(["add", "feature.py"], cwd=wt)
    _git(["commit", "-m", "add feature"], cwd=wt)

    wip_content = "# repo\n\nUSER WIP (do not lose this)\n"
    (repo / "README.md").write_text(wip_content)
    _git(["add", "README.md"], cwd=repo)

    wt_name = wt.name  # captured before cleanup destroys the directory
    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0

    # Ref file MUST exist after stage-only with dirty base
    ref_file = repo / ".claude" / f".hm-finalize-stash-{wt_name}"
    assert ref_file.is_file(), f"ref file must exist at {ref_file}"

    # Ref file body has the four required fields (ADR-001 §2)
    body = ref_file.read_text()
    assert "ref: stash@{" in body, f"ref: line missing. body: {body!r}"
    assert f"base: {repo.resolve()}" in body, f"base: line missing. body: {body!r}"
    assert "session:" in body, f"session: line missing. body: {body!r}"
    assert "created_at:" in body, f"created_at: line missing. body: {body!r}"

    # Stash itself MUST still exist (not popped yet — handed off to wrapup)
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert f"hm-finalize-{wt_name}" in stash_list, (
        f"stash must still exist after stage-only finalize. list: {stash_list!r}"
    )

    # Index has the squash result staged
    index = _git(["diff", "--cached", "--name-only"], cwd=repo).stdout
    assert "feature.py" in index, f"feature.py must be staged. index: {index!r}"

    # Working tree does NOT have the WIP README (it's in the stash) — this is
    # how stage-only achieves isolation: stashed user dirty stays out of the way
    # until wrapup commits its scoped paths, then post-commit-pop restores it.
    assert (repo / "README.md").read_text() != wip_content, (
        "user dirty must be stashed (not in working tree) during stage-only handoff"
    )


def test_stage_only_skips_ref_file_when_clean(repo: Path) -> None:
    """Stage-only with clean base: no stash, no ref file, behavior identical to pre-PLAN."""
    (wt,) = worktree.create("execute", repo)
    (wt / "feature.py").write_text("def feature() -> None:\n    pass\n")
    _git(["add", "feature.py"], cwd=wt)
    _git(["commit", "-m", "add feature"], cwd=wt)

    wt_name = wt.name
    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0

    ref_file = repo / ".claude" / f".hm-finalize-stash-{wt_name}"
    assert not ref_file.exists(), f"ref file must NOT exist when base was clean: {ref_file}"

    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert "hm-finalize-" not in stash_list, (
        f"no stash should be created when base is clean. list: {stash_list!r}"
    )


def test_post_commit_pop_happy_path(repo: Path) -> None:
    """post-commit-pop reads ref → session match → pops → restores WIP → deletes ref file."""
    (wt,) = worktree.create("execute", repo)
    (wt / "feature.py").write_text("def feature() -> None:\n    pass\n")
    _git(["add", "feature.py"], cwd=wt)
    _git(["commit", "-m", "add feature"], cwd=wt)

    wip_content = "# repo\n\nUSER WIP\n"
    (repo / "README.md").write_text(wip_content)
    _git(["add", "README.md"], cwd=repo)

    wt_name = wt.name
    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0

    # Simulate wrapup's commit: commit the staged squash (feature.py only).
    # This is the simplified version — real wrapup adds memory + PLAN paths too.
    _git(["commit", "-m", "wrapup: stage-only result"], cwd=repo)

    # Now invoke post-commit-pop
    rc2 = worktree._cli_post_commit_pop([str(repo)])
    assert rc2 == 0, "post-commit-pop happy path returns 0"

    # Ref file deleted on successful pop
    ref_file = repo / ".claude" / f".hm-finalize-stash-{wt_name}"
    assert not ref_file.exists(), "ref file must be deleted after successful pop"

    # Stash drained
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert f"hm-finalize-{wt_name}" not in stash_list, (
        f"stash should be drained after pop. list: {stash_list!r}"
    )

    # README restored to WIP, unstaged
    assert (repo / "README.md").read_text() == wip_content
    post_status = _porcelain(repo)
    assert " M README.md" in post_status, (
        f"README should be unstaged-modified after pop. status: {post_status!r}"
    )


def test_post_commit_pop_skips_stale_session(repo: Path, tmp_path: Path) -> None:
    """post-commit-pop SKIPS refs whose session marker is not currently active.

    Reproduces validator 2nd-pass warning #3: prior session left a ref file behind
    (no wrapup ran), a NEW session starts work, and its wrapup must not pop the
    stale stash from the prior session (which would silently contaminate this
    session's commit with the prior session's WIP).
    """
    # Create a stale ref file with a session marker that has no live marker on disk
    claude_dir = repo / ".claude"
    claude_dir.mkdir(exist_ok=True)
    stale_ref = claude_dir / ".hm-finalize-stash-execute-staleZ"
    stale_ref.write_text(
        "ref: stash@{0}\n"
        f"base: {repo.resolve()}\n"
        "session: .hm-loop-execute-staleZ\n"
        "created_at: 2026-01-01T00:00:00+00:00\n"
    )
    # Also create a real stash on the repo so the pop would have something to pop
    # if the session check weren't enforced.
    (repo / "junk.txt").write_text("from prior session\n")
    _git(["add", "junk.txt"], cwd=repo)
    _git(["stash", "push", "-u", "-m", "hm-finalize-execute-staleZ"], cwd=repo)

    # Sanity: stash exists, no .hm-loop-* marker (no active session)
    assert "hm-finalize-execute-staleZ" in _git(["stash", "list"], cwd=repo).stdout
    assert not list(claude_dir.glob(".hm-loop-*")), "no active session marker"

    rc = worktree._cli_post_commit_pop([str(repo)])
    assert rc == 0, "stale-session skip is a non-failing notice, not an error"

    # Ref file MUST remain (not deleted — user resolves manually or next session)
    assert stale_ref.exists(), "stale ref must NOT be deleted by session-mismatched pop"
    # Stash MUST remain
    assert "hm-finalize-execute-staleZ" in _git(["stash", "list"], cwd=repo).stdout, (
        "stale stash must NOT be popped"
    )
