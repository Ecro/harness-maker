"""Phase 4 (ADR-003): wrapup auto squash-land.

`task_land(base, slug)` squash-merges `hm/<slug>` onto the base's current branch
as a single conventional commit, then tears down (worktree + branch + registry
row), all inside the merge fence; a base-dirty guard aborts rather than clobber
user edits, and a landed-marker + content-in-HEAD check make a re-run idempotent
(partial-land recovery). Drain runs after the fence releases.
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


def _commit_count(repo: Path) -> int:
    return int(_git(["rev-list", "--count", "HEAD"], repo))


def _branches(repo: Path) -> list[str]:
    return _git(["branch", "--format=%(refname:short)"], repo).split()


def _landed_markers(repo: Path) -> str:
    return _git(["for-each-ref", "--format=%(refname)", "refs/hm-landed/"], repo)


def _make_task_with_committed_work(repo: Path, slug: str, *, content: str = "work\n") -> Path:
    """A task worktree on hm/<slug> with one committed edit on the branch."""
    wt = worktree.task_create(repo, slug, session_uuid=f"u-{slug}")
    (wt / "feature.py").write_text(content)
    _git(["add", "-A"], wt)
    _git(["commit", "-m", f"wip(execute): {slug}"], wt)
    return wt


# ── happy land ───────────────────────────────────────────────────────────────


def test_task_land_squashes_and_tears_down(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = _commit_count(repo)
    wt = _make_task_with_committed_work(repo, "feat")

    rc = worktree.task_land(repo, "feat")

    assert rc == 0
    # exactly ONE new commit on the base branch (squash)
    assert _commit_count(repo) == before + 1
    # the branch's work is now in base HEAD
    assert "feature.py" in _git(["ls-tree", "-r", "--name-only", "HEAD"], repo).split()
    # teardown: branch gone, worktree gone, registry row gone
    assert "hm/feat" not in _branches(repo)
    assert not wt.is_dir()
    assert worktree._read_sessions(repo) == []
    # the orphan landed-marker was reaped by the post-fence drain
    assert _landed_markers(repo) == ""


def test_task_land_uses_conventional_message(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _make_task_with_committed_work(repo, "feat")
    worktree.task_land(repo, "feat", message="feat(feat): add the feature")
    assert _git(["log", "-1", "--format=%s"], repo) == "feat(feat): add the feature"


# ── base-cleanliness abort (ADR-007 non-contact) ─────────────────────────────


def test_task_land_aborts_on_user_dirty_base(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = _commit_count(repo)
    wt = _make_task_with_committed_work(repo, "feat")
    (repo / "user_wip.py").write_text("user's uncommitted work\n")  # base dirt

    rc = worktree.task_land(repo, "feat")

    assert rc == 1
    assert _commit_count(repo) == before  # no squash commit created
    assert "hm/feat" in _branches(repo)  # branch preserved
    assert wt.is_dir()  # worktree preserved
    assert (repo / "user_wip.py").read_text() == "user's uncommitted work\n"  # untouched


def test_task_land_claude_churn_does_not_block(tmp_path: Path) -> None:
    """Operational `.claude/` churn is NOT user dirt — the land proceeds."""
    repo = _repo(tmp_path)
    obs = repo / ".claude" / "observability"
    obs.mkdir(parents=True, exist_ok=True)
    (obs / "metrics.jsonl").write_text('{"e":1}\n')  # gitignored churn

    _make_task_with_committed_work(repo, "feat")
    rc = worktree.task_land(repo, "feat")
    assert rc == 0
    assert "hm/feat" not in _branches(repo)


# ── idempotency / partial-land recovery ──────────────────────────────────────


def test_task_land_fully_landed_rerun_is_noop(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _make_task_with_committed_work(repo, "feat")
    assert worktree.task_land(repo, "feat") == 0
    count_after = _commit_count(repo)
    # re-run with branch + worktree already gone → idempotent no-op
    assert worktree.task_land(repo, "feat") == 0
    assert _commit_count(repo) == count_after  # no second commit


def test_task_land_partial_recovery_no_double_commit(tmp_path: Path) -> None:
    """Crash after squash+commit but before teardown → re-run finishes teardown
    WITHOUT a second commit (content already in HEAD)."""
    repo = _repo(tmp_path)
    wt = _make_task_with_committed_work(repo, "feat")
    # simulate the partial state: squash+commit done by hand, marker written,
    # but worktree + branch still present (teardown not yet run).
    _git(["merge", "--squash", "hm/feat"], repo)
    _git(["commit", "-m", "feat(feat): landed"], repo)
    worktree._write_landed_marker(repo, "hm/feat")
    committed = _commit_count(repo)
    assert wt.is_dir()
    assert "hm/feat" in _branches(repo)

    rc = worktree.task_land(repo, "feat")

    assert rc == 0
    assert _commit_count(repo) == committed  # NO double commit
    assert not wt.is_dir()
    assert "hm/feat" not in _branches(repo)
    assert worktree._read_sessions(repo) == []


def test_task_land_squash_conflict_resets_and_preserves(tmp_path: Path) -> None:
    """A conflicting change already on base → land aborts, base reset clean, the
    task branch preserved for manual resolution (no partial squash staged).

    Strengthened (validator W4): the branch ALSO adds a non-conflicting new file
    (`extra.py`) so the failed squash leaves untracked residue — and the base
    carries a pre-existing untracked DELIVERABLE the cleanliness gate forgives.
    The conflict cleanup must remove ONLY the merge residue, never the deliverable.
    """
    repo = _repo(tmp_path)
    wt = worktree.task_create(repo, "feat", session_uuid="u-feat")
    (wt / "feature.py").write_text("branch version\n")
    (wt / "extra.py").write_text("branch-only new file\n")  # non-conflicting add
    _git(["add", "-A"], wt)
    _git(["commit", "-m", "wip(execute): feat"], wt)
    # base gets a conflicting feature.py (add/add divergence vs the branch)
    (repo / "feature.py").write_text("base version\n")
    _git(["add", "feature.py"], repo)
    _git(["commit", "-m", "base adds feature.py differently"], repo)
    # a pre-existing untracked deliverable on base (forgiven by the dirty gate)
    (repo / "work-docs").mkdir(exist_ok=True)
    (repo / "work-docs" / "PLAN-keepme.md").write_text("user's plan\n")
    before = _commit_count(repo)

    rc = worktree.task_land(repo, "feat")

    assert rc == 1
    assert _commit_count(repo) == before  # no land commit
    assert "hm/feat" in _branches(repo)  # branch preserved for re-run
    assert wt.is_dir()
    assert (repo / "feature.py").read_text() == "base version\n"
    # merge residue removed; pre-existing untracked deliverable PRESERVED
    assert not (repo / "extra.py").exists()
    assert (repo / "work-docs" / "PLAN-keepme.md").read_text() == "user's plan\n"
    # base is clean except the user's own untracked deliverable (git collapses
    # the fully-untracked dir in default porcelain)
    assert _git(["status", "--porcelain"], repo) == "?? work-docs/"


def test_task_land_partial_recovery_worktree_gone_branch_present(tmp_path: Path) -> None:
    """Crash-point (iii): worktree already removed, branch + row still present →
    re-run converges (skips cleanup, deletes branch, drops row) with no raise and
    no double commit (validator critical #2)."""
    repo = _repo(tmp_path)
    wt = _make_task_with_committed_work(repo, "feat")
    # simulate: squash+commit done, marker written, worktree removed — but the
    # branch + registry row not yet cleaned (crash between the two).
    _git(["merge", "--squash", "hm/feat"], repo)
    _git(["commit", "-m", "feat(feat): landed"], repo)
    worktree._write_landed_marker(repo, "hm/feat")
    _git(["worktree", "remove", "--force", str(wt)], repo)
    assert not wt.is_dir()
    assert "hm/feat" in _branches(repo)
    committed = _commit_count(repo)

    rc = worktree.task_land(repo, "feat")

    assert rc == 0
    assert _commit_count(repo) == committed  # no double commit
    assert "hm/feat" not in _branches(repo)
    assert worktree._read_sessions(repo) == []
    assert _landed_markers(repo) == ""


def test_task_land_preserves_foreign_uuid_row(tmp_path: Path) -> None:
    """ADR-004: a same-branch row owned by a DIFFERENT live session_uuid must NOT
    be deleted by our land (validator W5)."""
    repo = _repo(tmp_path)
    # the registry row is owned by a foreign session...
    _make_task_with_committed_work(repo, "feat")  # registers uuid "u-feat"
    rows_before = worktree._read_sessions(repo)
    assert [r.session_uuid for r in rows_before] == ["u-feat"]

    # ...and WE land with a different uuid → the foreign row is preserved.
    rc = worktree.task_land(repo, "feat", session_uuid="u-someone-else")

    assert rc == 0
    # the foreign row survives (its worktree is now gone; its own reclaim drops it)
    assert [r.session_uuid for r in worktree._read_sessions(repo)] == ["u-feat"]


def test_task_land_captures_uncommitted_worktree_work(tmp_path: Path) -> None:
    """REVIEW code P1: uncommitted worktree edits must NOT be lost to the
    force-teardown — `task_land` captures them onto the branch before squashing."""
    repo = _repo(tmp_path)
    wt = worktree.task_create(repo, "feat", session_uuid="u-feat")
    (wt / "uncommitted.py").write_text("never committed\n")  # NOT committed

    rc = worktree.task_land(repo, "feat")

    assert rc == 0
    # the uncommitted work survived — captured onto the branch and squashed in
    assert "uncommitted.py" in _git(["ls-tree", "-r", "--name-only", "HEAD"], repo).split()
    assert not wt.is_dir()


def test_task_land_rejects_invalid_slug(tmp_path: Path) -> None:
    """REVIEW code P1: a force-removing entry must validate the slug (path-escape)."""
    repo = _repo(tmp_path)
    assert worktree.task_land(repo, "../escape") == 1
    assert worktree.task_land(repo, "a/b") == 1


def test_task_land_marker_survives_base_advance(tmp_path: Path) -> None:
    """REVIEW Codex P0: after a partial land, a later base-HEAD advance can make
    `_branch_content_in_head` False — the landed-marker (== branch tip) must still
    recognize already-landed so a re-run does NOT double-squash."""
    repo = _repo(tmp_path)
    wt = _make_task_with_committed_work(repo, "feat", content="branch v\n")
    # partial land done by hand: squash+commit + marker, worktree+branch kept.
    _git(["merge", "--squash", "hm/feat"], repo)
    _git(["commit", "-m", "feat(feat): landed"], repo)
    worktree._write_landed_marker(repo, "hm/feat")
    # base advances, modifying the SAME file → content-in-head would now be False
    (repo / "feature.py").write_text("base advanced the file\n")
    _git(["add", "feature.py"], repo)
    _git(["commit", "-m", "base advance"], repo)
    committed = _commit_count(repo)

    rc = worktree.task_land(repo, "feat")

    assert rc == 0
    assert _commit_count(repo) == committed  # NO double squash (marker==tip caught it)
    assert "hm/feat" not in _branches(repo)
    assert not wt.is_dir()


def test_task_land_no_uuid_preserves_foreign_live_pid_row(tmp_path: Path) -> None:
    """REVIEW Codex P1 / concurrency C2: the no-uuid CLI fallback must NOT delete a
    row owned by a DIFFERENT live session (ADR-004) — distinguished by pid."""
    import dataclasses
    import subprocess as sp

    repo = _repo(tmp_path)
    _make_task_with_committed_work(repo, "feat")  # row registered with our pid
    child = sp.Popen(["sleep", "30"])  # a real foreign-but-LIVE pid  # noqa: S603,S607
    try:
        worktree._registry_mutate(
            repo, lambda rows: [dataclasses.replace(r, pid=child.pid) for r in rows]
        )
        rc = worktree.task_land(repo, "feat")  # own=None (CLI fallback)
        assert rc == 0
        # foreign live-pid row PRESERVED; branch still torn down
        assert [r.pid for r in worktree._read_sessions(repo)] == [child.pid]
        assert "hm/feat" not in _branches(repo)
    finally:
        child.terminate()
        child.wait()


def test_task_land_cli_dispatch_is_wired(tmp_path: Path) -> None:
    """REVIEW (round 2): the `task-land` subcommand must actually be dispatched by
    main() — not fall through to 'unknown subcommand'."""
    repo = _repo(tmp_path)
    _make_task_with_committed_work(repo, "feat")
    rc = worktree.main(["task-land", "feat", str(repo), "--message", "feat(feat): via cli"])
    assert rc == 0
    assert "hm/feat" not in _branches(repo)
    assert _git(["log", "-1", "--format=%s"], repo) == "feat(feat): via cli"


def test_task_land_missing_branch_with_worktree_is_inconsistent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = _make_task_with_committed_work(repo, "feat")
    # git refuses to delete a branch checked out in a worktree, so detach the
    # worktree HEAD first, then drop the branch ref → branch-missing+wt-present.
    _git(["checkout", "--detach"], wt)
    _git(["branch", "-D", "hm/feat"], repo)
    assert wt.is_dir()
    assert "hm/feat" not in _branches(repo)
    # branch missing but worktree present → inconsistent → rc=1, preserved
    assert worktree.task_land(repo, "feat") == 1
    assert wt.is_dir()


# ── cross-session: squash must NOT sweep concurrent pre-staged base churn ─────


def test_task_land_does_not_sweep_concurrent_staged_base_churn(tmp_path: Path) -> None:
    # Codex P1 (empirically confirmed): `git merge --squash` + `git commit` with NO
    # pathspec commits the WHOLE index, so a concurrent session's pre-staged base
    # churn — `.claude/` + deliverables are EXCLUDED by the dirty-base guard, so it
    # does NOT abort — gets swept into THIS task's squash commit (the count:3
    # contamination class). The land must commit ONLY the squash's own path set.
    repo = _repo(tmp_path)
    _make_task_with_committed_work(repo, "feat", content="feat work\n")
    # Concurrent session stages an unrelated base file the dirty-base guard excludes
    # (`.claude/` is force-added past the fixture's gitignore to mimic the real repo
    # where `.claude/memory/wiki.md` is tracked-but-under-gitignored-`.claude/`).
    mem = repo / ".claude" / "memory"
    mem.mkdir(parents=True)
    (mem / "wiki.md").write_text("concurrent session note\n")
    _git(["add", "-f", ".claude/memory/wiki.md"], repo)

    assert worktree.task_land(repo, "feat") == 0

    landed = _git(["show", "--name-only", "--format=", "HEAD"], repo).split()
    assert "feature.py" in landed
    assert ".claude/memory/wiki.md" not in landed, "concurrent base churn swept into squash commit"
    # The concurrent file must survive untouched (not lost, not committed by us) AND
    # stay STAGED for its owning session — the actual cross-session contract.
    assert (mem / "wiki.md").read_text() == "concurrent session note\n"
    assert ".claude/memory/wiki.md" in _git(["diff", "--cached", "--name-only"], repo).split(), (
        "concurrent session's staged change must remain staged after our land"
    )


def test_task_land_records_rename_under_diff_renames_config(tmp_path: Path) -> None:
    # Codex P1: `_squash_path_set` uses `git diff --name-only`; with a user's
    # `diff.renames=true` a rename is reported as ONLY the destination path, so a
    # whole-index-vs-scoped commit could miss the staged DELETION of the old path —
    # the renamed-away file would linger in HEAD. `--no-renames` makes it two entries.
    repo = _repo(tmp_path)
    _git(["config", "diff.renames", "true"], repo)  # the adversarial user config
    # Seed a file on base, then a task branch that RENAMES it.
    (repo / "old_name.py").write_text("x = 1\n" * 20)
    _git(["add", "old_name.py"], repo)
    _git(["commit", "-m", "seed file to rename"], repo)
    wt = worktree.task_create(repo, "ren", session_uuid="u-ren")
    _git(["mv", "old_name.py", "new_name.py"], wt)
    _git(["commit", "-m", "wip(execute): rename"], wt)

    assert worktree.task_land(repo, "ren") == 0

    # After land: old path GONE from HEAD, new path present, no staged-deletion residue.
    head_files = _git(["ls-tree", "-r", "--name-only", "HEAD"], repo).split()
    assert "new_name.py" in head_files
    assert "old_name.py" not in head_files, "rename's old path lingered in HEAD (missed deletion)"
    assert _git(["status", "--porcelain"], repo) == "", "no staged-deletion residue left in base"
