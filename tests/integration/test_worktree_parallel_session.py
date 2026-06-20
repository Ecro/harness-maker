"""Phase 0 RED — cross-session worktree contamination integration test.

PLAN-worktree-cross-session-data-loss-defense Phase 0 exit criterion (a):
'tests/integration/test_worktree_parallel_session.py exists, RED for the
contamination case (proves the test catches the regression)'.

Failure pattern (3rd incident, 2026-05-23 wrapup):
    Session A's `worktree finalize stage-only` writes
    `.claude/.hm-finalize-stash-execute-A` ref file + a real `git stash` of
    base's dirty WIP. Session B's `/hm:wrapup post-commit-pop` iterates
    `glob('.claude/.hm-finalize-stash-*')` and tries to pop EVERY ref file,
    including Session A's. The existing `_session_marker_present(path)`
    helper returns True for ANY marker file that exists on disk — cross-
    session ownership is not enforced.

This test simulates two sessions writing finalize-stash ref files in the same
base repo, then asserts that `_cli_post_commit_pop` running as Session B does
NOT attempt to pop Session A's stash. Currently this assertion FAILS —
that's the RED gate.

Once Phase 3 (ADR-004 Session UUID + `_session_owns_marker`) lands, this
test should turn GREEN.

This test runs inside `tmp_path` with `git init` — never touches the real
repo. Wall-time budget per Phase 7 ADR: ≤ 30s total.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker import worktree

# Skip in default pytest run until Phase 7 promotes it; keep this guard until
# the promote-to-CI-always-run commit lands. Set HM_RUN_PARALLEL_SESSION=1 to
# exercise the RED case locally.
pytestmark = pytest.mark.skipif(
    os.getenv("HM_RUN_PARALLEL_SESSION") != "1",
    reason="Phase 0 RED — opt-in via HM_RUN_PARALLEL_SESSION=1 (promoted to "
    "always-run in Phase 7 after ADR-007 sandbox gitignore eliminates "
    "false-positives from snapshot/fixture re-render churn).",
)


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command with check=True + capture; tests must read stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )


def _init_base_repo(tmp_path: Path) -> Path:
    """Create an isolated git repo with one commit so stash can operate."""
    repo = tmp_path / "base-repo"
    repo.mkdir()
    _git("init", "-b", "main", ".", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git("add", "README.md", cwd=repo)
    _git("commit", "-m", "init", cwd=repo)
    return repo


def _create_stash(repo: Path, session_id: str, dirty_content: str) -> str:
    """Create a real `git stash` entry. Returns its SHA.

    `git stash push -u` would capture the `.claude/` dir if it already
    existed in the WT, so the caller must NOT create `.claude/` until all
    stashes are made (otherwise the second `stash -u` swallows the first
    session's marker + ref file as 'untracked' and the contamination case
    can't be exercised). See `_setup_two_sessions` for the required order.
    """
    (repo / f"dirty-{session_id}.txt").write_text(dirty_content, encoding="utf-8")
    _git("stash", "push", "-u", "-m", f"hm-finalize-execute-{session_id}-fixture", cwd=repo)
    return _git("rev-parse", "stash@{0}", cwd=repo).stdout.strip()


def _create_session_ref(repo: Path, session_id: str, stash_sha: str, session_uuid: str) -> None:
    """Write the session marker + finalize-stash ref file (no git stash).

    `session_uuid` is the 12-hex UUID identifying the session that wrote this
    ref. Phase 3 ADR-004 enforcement: `_cli_post_commit_pop` skips refs whose
    `session_uuid` doesn't match the current process's UUID.
    """
    claude_dir = repo / ".claude"
    claude_dir.mkdir(exist_ok=True)
    marker = claude_dir / f".hm-loop-{session_id}"
    marker.write_text(f"session={session_id}\n", encoding="utf-8")
    ref_file = claude_dir / f".hm-finalize-stash-execute-{session_id}"
    ref_file.write_text(
        f"ref_sha: {stash_sha}\n"
        f"base: {repo}\n"
        f"session_marker: {marker}\n"
        f"sibling_bases: \n"
        f"session_uuid: {session_uuid}\n"
        f"created_at: 2026-05-23T13:36:00Z\n",
        encoding="utf-8",
    )


def _setup_two_sessions(repo: Path) -> tuple[str, str]:
    """Two ref files + ONE active loop marker (Session A's only).

    Phase 3 follow-up (dirname embed): post-commit-pop's ownership check now
    reads the set of UUIDs from active `.claude/.hm-loop-*` marker filenames
    (these correspond to the worktrees owned by THIS process). Only Session
    A's marker is created → A's UUID is in the owned set, B's is not.

    Expected behavior:
    - Session A's ref → UUID matches owned set → pop attempted (we want sha_a
      gone from list_after).
    - Session B's ref → UUID NOT in owned set → SKIP (sha_b stays in list).

    Test asserts sha_b survives (the cross-session-contamination guard works).
    """
    sha_a = _create_stash(repo, "session-A", "A\n")
    sha_b = _create_stash(repo, "session-B", "B\n")
    _create_session_ref(repo, "session-A", sha_a, session_uuid="aaaaaaaaaaaa")
    _create_session_ref(repo, "session-B", sha_b, session_uuid="bbbbbbbbbbbb")
    # Only Session A's loop marker exists — UUID aaaa... is in the owned set;
    # UUID bbbb... is NOT (Session B's wrapup hasn't run yet from THIS proc).
    claude_dir = repo / ".claude"
    (claude_dir / ".hm-loop-execute-aaaaaaaaaaaa-20260523T1336Z").write_text("x")
    return sha_a, sha_b


def test_post_commit_pop_does_not_touch_other_session_stash(tmp_path: Path) -> None:
    """RED until Phase 3 (ADR-004 Session UUID) lands.

    Setup: two sessions (A and B) each write a finalize-stash ref + a real
    git stash to the SAME base repo. Both session markers are live (is_file()
    True for both).

    Action: invoke `harness_maker.worktree post-commit-pop <base>` as if
    Session B were running wrapup.

    Assertion: Session A's stash MUST remain in the stash list — the
    post-commit-pop run from Session B must not own or touch it.

    Expected fail (current state): both stashes get popped because
    `_session_marker_present` returns True for both A's and B's markers,
    and the CLI iterates every glob match.
    """
    base = _init_base_repo(tmp_path)
    sha_a, sha_b = _setup_two_sessions(base)

    # Stash list should now have two entries — A and B.
    list_before = _git("stash", "list", "--format=%H", cwd=base).stdout.strip().splitlines()
    assert sha_a in list_before
    assert sha_b in list_before

    # Run post-commit-pop as if from Session B context. The CLI uses the
    # filesystem state to decide ownership; no environment hint distinguishes
    # session B from A — which is exactly the bug.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.worktree",
            "post-commit-pop",
            str(base),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )

    list_after = _git("stash", "list", "--format=%H", cwd=base).stdout.strip().splitlines()

    # DEBUG: assert proc completed and dump for diagnosis.
    diag = (
        f"\n=== post-commit-pop exit={proc.returncode}\n"
        f"=== stdout:\n{proc.stdout}\n"
        f"=== stderr:\n{proc.stderr}\n"
        f"=== stash list before: {[s[:8] for s in list_before]}\n"
        f"=== stash list after:  {[s[:8] for s in list_after]}\n"
        f"=== sha_a={sha_a[:8]} sha_b={sha_b[:8]}\n"
    )

    # CONTAMINATION ASSERTION: Session B's UUID is NOT in the owned set
    # (only A's loop marker exists). post-commit-pop MUST skip B's ref and
    # leave sha_b in the stash list. Pre-Phase-3-followup this failed
    # because UUID isolation was non-functional (project-scoped shared UUID).
    # Post-Phase-3-followup the dirname-embedded UUIDs make ownership a
    # real boundary.
    assert sha_b in list_after, (
        f"REGRESSION: Session B's stash {sha_b[:8]} was touched by "
        f"the current process's post-commit-pop despite B's UUID not "
        f"being in the owned set.{diag}"
    )


def _branch_exists(branch: str, repo: Path) -> bool:
    return branch in _git("branch", "--list", branch, cwd=repo).stdout


def test_create_time_prune_preserves_inflight_finalize_branch(tmp_path: Path) -> None:
    """P1 cross-session (PLAN-p6-p7-worktree-finalize ADR-002, exit criterion #4).

    Models session B's create-time `prune_stale` running while session A's
    stage-only finalize is mid-flight. After A's `finalize stage-only`, A's work
    is staged into the base index but NOT yet committed (wrapup commits later),
    A's worktree dir is gone, and A's `execute-*` branch + `wip(execute)` commit
    remain. B's orphan-branch sweep MUST preserve A's branch — A's content is
    not in HEAD, so the content-gate keeps it (never delete another session's
    unsaved work). Only once A's wrapup commits does a later prune sweep it.

    This is the net-new cross-session behavior assertion the PLAN requires on
    top of the single-session unit tests — "existing GREEN" cannot catch it.
    """
    base = _init_base_repo(tmp_path)

    # Session A: create worktree, do work, commit the wip(execute) commit.
    wt_a = worktree.create("execute", base)[0]
    branch_a = wt_a.name
    (wt_a / "feat.txt").write_text("A work\n", encoding="utf-8")
    _git("add", ".", cwd=wt_a)
    _git("commit", "-m", "wip(execute): A work", cwd=wt_a)

    # Session A's stage-only finalize: stages into base, removes the dir, keeps
    # the branch (the documented stash-conflict recovery net) — via the same CLI
    # /hm:execute uses.
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "finalize", str(wt_a), "stage-only"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"finalize stage-only failed: {proc.stderr}"
    assert not wt_a.exists(), "stage-only finalize should remove A's worktree dir"
    assert _branch_exists(branch_a, base), "finalize must NOT delete A's branch (recovery net)"

    # Session B's create-time prune, mid-flight: A's work is staged, NOT in HEAD.
    report_midflight = worktree.prune_stale(base)
    assert _branch_exists(branch_a, base), (
        "cross-session: in-flight finalize branch must survive (content not in HEAD)"
    )
    assert any(branch_a == b for b, _hint in report_midflight.preserved_branches), (
        "A's branch must be reported preserved, not removed"
    )
    assert branch_a not in report_midflight.removed_branches

    # Session A's wrapup commits → A's work now lands in HEAD.
    _git("commit", "-m", "wrapup: land A work", cwd=base)

    # A later create-time prune now sweeps the orphan branch (content in HEAD).
    report_after = worktree.prune_stale(base)
    assert not _branch_exists(branch_a, base), (
        "after wrapup commit the orphan branch's content is in HEAD → swept"
    )
    assert branch_a in report_after.removed_branches


def test_flag_on_finalize_commit_not_stash(tmp_path: Path) -> None:
    """Phase 3 (ADR-007) flag-ON path: a task worktree's stage-only finalize
    captures pending work as a commit on `hm/<slug>` and never touches the base
    (no stash, no merge-to-base, no `.hm-finalize-stash-*` ref), leaving the
    persistent worktree in place for the Phase-4 land. Exercises the real CLI
    boundary (subprocess), mirroring how /hm:execute Step 5 invokes finalize.
    """
    base = _init_base_repo(tmp_path)
    claude = base / ".claude"
    claude.mkdir(exist_ok=True)
    (claude / "harness.yaml").write_text(
        "worktree:\n  feature_branch_workflow: true\n", encoding="utf-8"
    )
    base_head = _git("rev-parse", "HEAD", cwd=base).stdout.strip()

    wt = worktree.task_create(base, "lifecycle", session_uuid="u-int-1")
    (wt / "feature.py").write_text("print('work')\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "finalize", str(wt), "stage-only"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"flag-ON finalize failed: {proc.stderr}"
    # persistent worktree survives (land owns teardown, not finalize)
    assert wt.is_dir()
    # pending work is a reachable commit on the task branch
    tree = _git("ls-tree", "-r", "--name-only", "hm/lifecycle", cwd=base).stdout
    assert "feature.py" in tree.split()
    # the CLI boundary actually CREATED a wip commit (tip advanced past base HEAD)
    assert "wip" in _git("log", "--oneline", "hm/lifecycle", cwd=base).stdout.lower()
    assert _git("rev-parse", "hm/lifecycle", cwd=base).stdout.strip() != base_head
    # base never touched: HEAD unchanged + zero finalize-stash refs anywhere
    assert _git("rev-parse", "HEAD", cwd=base).stdout.strip() == base_head
    assert sorted((base / ".claude").glob(".hm-finalize-stash-*")) == []


def test_concurrent_task_lands_serialize_under_fence(tmp_path: Path) -> None:
    """Phase 4 (ADR-003) exit-criterion (a)+(b): two concurrent `task_land` calls
    on DISTINCT slugs both squash onto the shared base branch. They serialize
    under the merge fence (flock primary / O_EXCL secondary, WSL2-reliable) so
    both land exactly once with no contamination — without the fence the two
    `git commit`s on the shared base index would race/corrupt.
    """
    import concurrent.futures

    base = _init_base_repo(tmp_path)
    before = int(_git("rev-list", "--count", "HEAD", cwd=base).stdout.strip())

    for slug, content in (("feat-a", "AAA\n"), ("feat-b", "BBB\n")):
        wt = worktree.task_create(base, slug, session_uuid=f"u-{slug}")
        (wt / f"{slug}.py").write_text(content, encoding="utf-8")
        _git("add", "-A", cwd=wt)
        _git("commit", "-m", f"wip(execute): {slug}", cwd=wt)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(lambda s: worktree.task_land(base, s), ["feat-a", "feat-b"]))

    assert results == [0, 0], f"both lands must succeed: {results}"
    # exactly TWO new squash commits on base (one per task, serialized)
    after = int(_git("rev-list", "--count", "HEAD", cwd=base).stdout.strip())
    assert after == before + 2
    # both branches + worktrees torn down, both rows gone, no leaked markers
    branches = _git("branch", "--format=%(refname:short)", cwd=base).stdout.split()
    assert "hm/feat-a" not in branches
    assert "hm/feat-b" not in branches
    assert not (base / ".worktrees" / "feat-a").is_dir()
    assert not (base / ".worktrees" / "feat-b").is_dir()
    assert worktree._read_sessions(base) == []
    assert _git("for-each-ref", "--format=%(refname)", "refs/hm-landed/", cwd=base).stdout == ""
    # both tasks' content actually landed in base HEAD (no contamination / loss)
    tree = _git("ls-tree", "-r", "--name-only", "HEAD", cwd=base).stdout.split()
    assert "feat-a.py" in tree
    assert "feat-b.py" in tree


def test_concurrent_lands_serialize_via_oexcl_secondary(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Phase 4 exit-criterion (b) / REVIEW concurrency C3: force the WSL2-reliable
    O_EXCL secondary lock leg (flock reported unsupported) and prove two concurrent
    lands still serialize and both land exactly once."""
    import concurrent.futures

    # Force `_acquire_merge_fence` onto the O_EXCL secondary mechanism.
    monkeypatch.setattr(worktree, "_flock_lock", lambda path, timeout: (None, "unsupported"))

    base = _init_base_repo(tmp_path)
    before = int(_git("rev-list", "--count", "HEAD", cwd=base).stdout.strip())
    for slug, content in (("ox-a", "A\n"), ("ox-b", "B\n")):
        wt = worktree.task_create(base, slug, session_uuid=f"u-{slug}")
        (wt / f"{slug}.py").write_text(content, encoding="utf-8")
        _git("add", "-A", cwd=wt)
        _git("commit", "-m", f"wip(execute): {slug}", cwd=wt)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(lambda s: worktree.task_land(base, s), ["ox-a", "ox-b"]))

    assert results == [0, 0], f"both lands must succeed via O_EXCL: {results}"
    after = int(_git("rev-list", "--count", "HEAD", cwd=base).stdout.strip())
    assert after == before + 2  # serialized: exactly two squash commits
    branches = _git("branch", "--format=%(refname:short)", cwd=base).stdout.split()
    assert "hm/ox-a" not in branches
    assert "hm/ox-b" not in branches
    assert worktree._read_sessions(base) == []
