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


def test_task_land_prints_fresh_squash_sha_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REVIEW P2: the fresh-squash path prints its new commit SHA as the only stdout line;
    converge / already-landed runs print nothing — wrapup anchors the memory fold's
    `--expect-head` on this in-fence SHA, never a race-prone post-hoc `rev-parse`."""
    repo = _repo(tmp_path)
    _make_task_with_committed_work(repo, "feat")
    assert worktree.task_land(repo, "feat") == 0
    out = capsys.readouterr().out.strip()
    head = _git(["rev-parse", "HEAD"], repo)
    assert out == head, "fresh squash must print exactly the new HEAD SHA to stdout"
    # a fully-landed re-run converges and prints NOTHING to stdout (no SHA to fold against)
    assert worktree.task_land(repo, "feat") == 0
    assert capsys.readouterr().out.strip() == "", "converge/no-op land must not print a SHA"


def test_task_land_uses_conventional_message(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _make_task_with_committed_work(repo, "feat")
    worktree.task_land(repo, "feat", message="feat(feat): add the feature")
    assert _git(["log", "-1", "--format=%s"], repo) == "feat(feat): add the feature"


def test_task_land_reuses_branch_tip_message_when_none_given(tmp_path: Path) -> None:
    # REVIEW-2026-06-21 P2-3: with no explicit --message, the squash must reuse the
    # branch tip's curated commit message (the wrapup why-message + Co-Authored-By),
    # NOT a generic `chore(<slug>): squash-land` placeholder that drops the rationale.
    repo = _repo(tmp_path)
    wt = worktree.task_create(repo, "feat", session_uuid="u-feat")
    (wt / "feature.py").write_text("feat\n")
    _git(["add", "-A"], wt)
    coauthor = "Co-Authored-By: Claude <noreply@anthropic.com>"
    body = f"feat(feat): add the widget\n\nWhy: users needed it.\n\n{coauthor}"
    _git(["commit", "-m", body], wt)

    assert worktree.task_land(repo, "feat") == 0

    landed = _git(["log", "-1", "--format=%B"], repo)
    assert landed.splitlines()[0] == "feat(feat): add the widget", "subject not from branch tip"
    assert "Why: users needed it." in landed, "why-body lost in the squash"
    assert coauthor in landed, "Co-Authored-By trailer lost"
    assert "squash-land" not in landed, "fell back to the generic placeholder message"


def test_task_land_converges_when_branch_change_already_in_head(tmp_path: Path) -> None:
    # REVIEW-2026-06-21 P2-2: when base HEAD already contains the branch's change
    # (a prior land / cherry-pick / subset edit), `_branch_content_in_head` still
    # reports a per-blob mismatch so `already` is False, but `git merge --squash`
    # stages NOTHING. The old code let `git commit` fail "nothing to commit" and
    # routed to the conflict path → the land NEVER converged (branch/worktree/row
    # leaked indefinitely). It must instead converge to a clean teardown (rc0, no
    # new commit), exactly like the already-landed path.
    repo = _repo(tmp_path)
    lines = [f"line-{c}\n" for c in "abcdefghij"]
    (repo / "f.txt").write_text("".join(lines))
    _git(["add", "f.txt"], repo)
    _git(["commit", "-m", "seed f.txt"], repo)  # the merge-base
    # task branch changes ONE hunk (line c).
    wt = worktree.task_create(repo, "feat", session_uuid="u-feat")
    br = list(lines)
    br[2] = "line-C\n"
    (wt / "f.txt").write_text("".join(br))
    _git(["add", "f.txt"], wt)
    _git(["commit", "-m", "wip(execute): change c"], wt)
    # base HEAD independently already has the SAME c-change PLUS an unrelated h-change,
    # so the branch's delta is present in HEAD yet the full-file blobs differ.
    base_head = list(lines)
    base_head[2] = "line-C\n"
    base_head[7] = "line-H\n"
    (repo / "f.txt").write_text("".join(base_head))
    _git(["add", "f.txt"], repo)
    _git(["commit", "-m", "base: c + h"], repo)

    before = _commit_count(repo)
    rc = worktree.task_land(repo, "feat")

    assert rc == 0, "content-equivalent land must converge, not fail as a conflict"
    assert _commit_count(repo) == before, "converge must not create a new commit"
    assert "hm/feat" not in _branches(repo), "branch leaked — land did not converge"
    assert not wt.is_dir(), "worktree leaked — land did not converge"
    assert worktree._read_sessions(repo) == [], "registry row leaked"
    # base HEAD content is untouched (the unrelated h-change preserved).
    assert (repo / "f.txt").read_text() == "".join(base_head)


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
    # The concurrent file must survive untouched (not lost, not committed by us). The
    # land commits the INDEX (REVIEW-2026-06-21 P2-1: never the working tree), so the
    # churn is UNSTAGED back to the working tree — content preserved for its owning
    # session to re-stage, never clobbered, never landed.
    assert (mem / "wiki.md").read_text() == "concurrent session note\n"
    # Not landed in our commit (checked above) and not in HEAD's tree at all — it
    # remains the concurrent session's own uncommitted work, preserved on disk.
    head_tree = _git(["ls-tree", "-r", "--name-only", "HEAD"], repo).split()
    assert ".claude/memory/wiki.md" not in head_tree


def test_task_land_lands_non_ascii_filename_and_leaves_base_clean(tmp_path: Path) -> None:
    # REVIEW-2026-06-21 P1-1: `git diff --name-only` C-quotes non-ASCII names under
    # the default core.quotepath=true; a quoted literal pathspec never matches → the
    # land aborts rc1 AND leaves the squash staged-orphaned in base (re-opening the
    # count:3 contamination class). `-z` enumeration + index-commit must land cleanly.
    repo = _repo(tmp_path)
    wt = worktree.task_create(repo, "i18n", session_uuid="u-i18n")
    (wt / "café.md").write_text("한국어 deliverable\n")  # non-ASCII filename
    (wt / "ascii_sibling.py").write_text("x = 1\n")
    _git(["add", "-A"], wt)
    _git(["commit", "-m", "wip(execute): i18n"], wt)

    assert worktree.task_land(repo, "i18n") == 0

    # core.quotepath=false so the non-ASCII name comes back raw, not C-quoted.
    head_files = _git(
        ["-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", "HEAD"], repo
    ).split()
    assert "café.md" in head_files, "non-ASCII deliverable failed to land"
    assert "ascii_sibling.py" in head_files, "ASCII sibling lost to all-or-nothing pathspec abort"
    assert _git(["status", "--porcelain"], repo) == "", "non-ASCII land left staged residue in base"
    assert "hm/i18n" not in _branches(repo)


def test_task_land_conflict_preserves_concurrent_staged_same_path(tmp_path: Path) -> None:
    # REVIEW-2026-06-21 P1-2: when the task branch touches the SAME guard-forgiven
    # path a concurrent session has staged in base, `git merge --squash` aborts and
    # `_scoped_conflict_cleanup` used to `reset`/`checkout -f HEAD` the colliding path
    # — clobbering the concurrent session's staged work (the contamination class the
    # scoped land defends against). The pre-staged set must be preserved.
    repo = _repo(tmp_path)
    # base seeds the shared deliverable so both sides diverge from a common ancestor.
    docs = repo / "work-docs"
    docs.mkdir()
    (docs / "PLAN-x.md").write_text("base original\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "seed deliverable"], repo)
    # task branch edits the deliverable + commits.
    wt = worktree.task_create(repo, "feat", session_uuid="u-feat")
    (wt / "work-docs" / "PLAN-x.md").write_text("branch edit\n")
    (wt / "feature.py").write_text("feat\n")
    _git(["add", "-A"], wt)
    _git(["commit", "-m", "wip(execute): feat"], wt)
    # concurrent session stages a DIFFERENT edit to the SAME deliverable in base
    # (deliverables are forgiven by the dirty-base guard → land does not abort early).
    (docs / "PLAN-x.md").write_text("CONCURRENT SESSION irreplaceable plan\n")
    _git(["add", "work-docs/PLAN-x.md"], repo)

    rc = worktree.task_land(repo, "feat")

    # land aborts on the merge conflict (rc1), branch + worktree preserved …
    assert rc == 1
    assert (repo / ".worktrees" / "feat").is_dir()
    assert "hm/feat" in _branches(repo)
    # … and the concurrent session's staged content is NOT clobbered.
    assert (docs / "PLAN-x.md").read_text() == "CONCURRENT SESSION irreplaceable plan\n", (
        "conflict-cleanup clobbered a concurrent session's staged work (P1-2)"
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
