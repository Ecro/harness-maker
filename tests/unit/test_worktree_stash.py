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
    (r / ".gitignore").write_text(".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n")
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

    # Ref file body has the four required fields (PLAN-worktree-stash-phase4 ADR-002)
    body = ref_file.read_text()
    import re

    sha_match = re.search(r"^ref_sha: ([0-9a-f]{40})$", body, re.MULTILINE)
    assert sha_match is not None, f"ref_sha line must contain a 40-char hex SHA. body: {body!r}"
    assert f"base: {repo.resolve()}" in body, f"base: line missing. body: {body!r}"
    # session_marker must be an absolute path pointing at the primary repo's marker
    expected_marker = repo.resolve() / ".claude" / f".hm-loop-{wt_name}"
    assert f"session_marker: {expected_marker}" in body, (
        f"session_marker line missing or wrong path. body: {body!r}"
    )
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
    # Create a stale ref file with the NEW schema (PLAN-worktree-stash-phase4 ADR-002).
    # Body must pass _validate_stash_ref_fields: valid SHA, absolute base + marker,
    # but the session_marker points at a path that doesn't exist (= stale).
    claude_dir = repo / ".claude"
    claude_dir.mkdir(exist_ok=True)
    stale_ref = claude_dir / ".hm-finalize-stash-execute-staleZ"
    # Use a real SHA so SHA validation passes — pick a deterministic 40-hex string.
    fake_sha = "a" * 40
    stale_marker = repo.resolve() / ".claude" / ".hm-loop-execute-staleZ"
    stale_ref.write_text(
        f"ref_sha: {fake_sha}\n"
        f"base: {repo.resolve()}\n"
        f"session_marker: {stale_marker}\n"
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


# ──────────────────────────────────────────────────────────────────────────────
# Phase 3 (PLAN-worktree-stash-phase4 ADR-003): full failure matrix.
# Cases 1, 2, 3, 4, 6, 7 map to ADR-003 mandates.
# ──────────────────────────────────────────────────────────────────────────────


def test_class_a_merge_conflict_pop(repo: Path) -> None:
    """ADR-003 case 1: stash apply on overlapping tracked file → merge conflict.

    Base has staged modification to README.md; worktree branch ALSO modifies
    README.md on different lines. After squash commits the branch's version,
    apply of stash creates `<<<<<<<` markers because the stashed content and
    the squashed result both touch README.md.
    """
    (wt,) = worktree.create("execute", repo)

    # Worktree branch modifies README differently from what's on main
    (wt / "README.md").write_text("# repo\n\nFROM WORKTREE BRANCH\n")
    _git(["add", "README.md"], cwd=wt)
    _git(["commit", "-m", "worktree changes README"], cwd=wt)

    # Base also modifies README with conflicting content + stages
    (repo / "README.md").write_text("# repo\n\nFROM BASE WIP\n")
    _git(["add", "README.md"], cwd=repo)

    rc = worktree._cli_finalize([str(wt), "success"])
    assert rc == 1, "merge-conflict-on-pop must return rc=1"

    # Stash MUST be preserved for manual recovery
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert "hm-finalize-" in stash_list, (
        f"stash must be preserved after conflict. list: {stash_list!r}"
    )


def test_class_b_untracked_collision_pop(repo: Path) -> None:
    """ADR-003 case 2: untracked file in base collides with newly-tracked file
    in worktree branch → apply refuses to restore the stashed untracked file.
    """
    (wt,) = worktree.create("execute", repo)

    # Worktree branch creates tracked `notes.txt`
    (wt / "notes.txt").write_text("from worktree\n")
    _git(["add", "notes.txt"], cwd=wt)
    _git(["commit", "-m", "add notes from worktree"], cwd=wt)

    # Base has an UNTRACKED notes.txt with different content
    (repo / "notes.txt").write_text("base scratch\n")

    rc = worktree._cli_finalize([str(wt), "success"])
    assert rc == 1, "untracked-collision must return rc=1"

    # Stash MUST be preserved
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert "hm-finalize-" in stash_list


def test_submodule_abort_prevents_stash(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-005 (parent PLAN): dirty submodule pointer aborts finalize BEFORE any stash.

    Real submodule setup is brittle on tmp_path; mock `_run` to return a synthetic
    `+abc... path` line for `git submodule status`.
    """
    (wt,) = worktree.create("execute", repo)
    (wt / "feature.py").write_text("pass\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "add"], cwd=wt)

    # Add some dirty work to base so we'd normally stash (then assert we didn't).
    (repo / "README.md").write_text("# repo\n\nWIP\n")
    _git(["add", "README.md"], cwd=repo)

    original_run = worktree._run

    def faked_run(args: list[str], cwd: Path, **kwargs: object) -> object:
        if args[:2] == ["git", "submodule"] and args[2:3] == ["status"]:

            class _FakeResult:
                stdout = "+abc123 mysubmodule (1.0.0-dirty)\n"

            return _FakeResult()
        return original_run(args, cwd, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(worktree, "_run", faked_run)

    rc = worktree._cli_finalize([str(wt), "success"])
    assert rc == 1, "submodule dirty must abort"

    # Stash must NOT have been created (abort happens before _stash_base_dirty)
    monkeypatch.setattr(worktree, "_run", original_run)
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert "hm-finalize-" not in stash_list, (
        f"submodule abort must prevent stash creation. list: {stash_list!r}"
    )


def test_cleanup_failure_after_squash_preserves_handoff(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-001 §4 (validator 2nd-pass critical): cleanup() failing AFTER squash
    + ref-file-write must NOT cause `finally:` to pop and re-contaminate the
    staged index. `handed_off` must be True before cleanup runs.
    """
    (wt,) = worktree.create("execute", repo)
    (wt / "feature.py").write_text("pass\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "add feature"], cwd=wt)

    # Base WIP
    (repo / "README.md").write_text("# repo\n\nWIP\n")
    _git(["add", "README.md"], cwd=repo)

    wt_name = wt.name
    # Inject cleanup failure
    monkeypatch.setattr(
        worktree,
        "cleanup",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("simulated cleanup fail")),
    )

    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 1, "cleanup failure must surface as rc=1"

    # Ref file MUST exist on disk — handed_off flipped BEFORE cleanup.
    ref_file = repo / ".claude" / f".hm-finalize-stash-{wt_name}"
    assert ref_file.is_file(), (
        f"ref file MUST persist even on cleanup failure. "
        f"If absent, cleanup ran before ref write or finally popped — bug. "
        f"Checked path: {ref_file}"
    )

    # Stash MUST still exist (not popped by finally)
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert "hm-finalize-" in stash_list, (
        "stash must NOT be popped on cleanup-failure path "
        f"(would re-contaminate staged squash). list: {stash_list!r}"
    )

    # Index must still contain the squash result (feature.py)
    index = _git(["diff", "--cached", "--name-only"], cwd=repo).stdout
    assert "feature.py" in index, f"staged squash must persist on cleanup failure. index: {index!r}"


# ──────────────────────────────────────────────────────────────────────────────
# Multi-repo coverage (REVIEW M-P0-1 + M-P0-2 fixes, M-P1-1 closure).
# Reuses the multi-repo fixture pattern from test_worktree_multi.py.
# ──────────────────────────────────────────────────────────────────────────────


def _make_multi_repo(path: Path) -> Path:
    """Mirror tests/unit/test_worktree_multi.py's _make_repo with .gitignore prep."""
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], cwd=path)
    _git(["config", "user.email", "t@t"], cwd=path)
    _git(["config", "user.name", "t"], cwd=path)
    (path / "README.md").write_text(f"# {path.name}\n")
    (path / ".gitignore").write_text(
        ".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n"
    )
    _git(["add", "."], cwd=path)
    _git(["commit", "-m", "init"], cwd=path)
    return path


@pytest.fixture
def multi_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Primary + 1 sibling repo. Sibling discovery is via the ref-file body
    (sibling_bases field) written by finalize — NOT via harness.yaml — so the
    fixture no longer needs to set up the yaml at all (REVIEW round 2 redesign).
    """
    primary = _make_multi_repo(tmp_path / "primary")
    sibling = _make_multi_repo(tmp_path / "sibling")
    return primary, sibling


def test_multi_repo_stage_only_pops_both_stashes(multi_repo: tuple[Path, Path]) -> None:
    """REVIEW M-P0-1 + M-P0-2: post-commit-pop must drain BOTH primary AND
    sibling stashes. Closes the test-coverage gap (M-P1-1) and the routing
    correctness gap in one verification.
    """
    primary, sibling = multi_repo

    # Create multi-repo worktrees
    wts = worktree.create("execute", primary, sibling_dirs=[sibling])
    assert len(wts) == 2, "create() must return [primary_wt, sibling_wt]"
    primary_wt, sibling_wt = wts

    # Worktree-side commits in BOTH repos
    (primary_wt / "primary_feature.py").write_text("primary\n")
    _git(["add", "."], cwd=primary_wt)
    _git(["commit", "-m", "primary feature"], cwd=primary_wt)

    (sibling_wt / "sibling_feature.py").write_text("sibling\n")
    _git(["add", "."], cwd=sibling_wt)
    _git(["commit", "-m", "sibling feature"], cwd=sibling_wt)

    # Pre-existing dirty WIP in BOTH bases
    primary_wip = "# primary\n\nPRIMARY USER WIP\n"
    (primary / "README.md").write_text(primary_wip)
    _git(["add", "README.md"], cwd=primary)

    sibling_wip = "# sibling\n\nSIBLING USER WIP\n"
    (sibling / "README.md").write_text(sibling_wip)
    _git(["add", "README.md"], cwd=sibling)

    # Stage-only finalize (creates ref files for BOTH repos)
    rc = worktree._cli_finalize([str(primary_wt), "stage-only"])
    assert rc == 0, f"stage-only finalize must succeed across both repos, got rc={rc}"

    # Ref files present in BOTH .claude dirs
    primary_refs = list((primary / ".claude").glob(".hm-finalize-stash-*"))
    sibling_refs = list((sibling / ".claude").glob(".hm-finalize-stash-*"))
    assert primary_refs, f"primary ref file missing: {list((primary / '.claude').iterdir())}"
    assert sibling_refs, (
        f"sibling ref file missing: {list((sibling / '.claude').iterdir())} — "
        f"PLAN ADR-002 requires per-repo ref files"
    )

    # Simulate wrapup commit (just commit the staged squash on primary; in
    # practice wrapup also adds memory + work-docs paths, but this test only
    # cares about the post-commit-pop routing).
    _git(["commit", "-m", "wrapup primary"], cwd=primary)
    _git(["commit", "-m", "wrapup sibling"], cwd=sibling)

    # ⭐ THE CORE ASSERTION: post-commit-pop on PRIMARY must discover + pop
    # the SIBLING stash too via harness.yaml.sibling_repos + ref-file `base`
    # routing. Before M-P0-1+M-P0-2 fixes, sibling stash was permanently leaked.
    rc2 = worktree._cli_post_commit_pop([str(primary)])
    assert rc2 == 0, f"post-commit-pop must succeed for multi-repo, got rc={rc2}"

    # BOTH user WIPs restored
    assert (primary / "README.md").read_text() == primary_wip, (
        "primary WIP must be restored after pop"
    )
    assert (sibling / "README.md").read_text() == sibling_wip, (
        "sibling WIP must be restored after pop — this assertion would have "
        "FAILED before M-P0-1+M-P0-2 fixes (sibling stash leaked)"
    )

    # Both stashes drained
    primary_stash = _git(["stash", "list"], cwd=primary).stdout
    sibling_stash = _git(["stash", "list"], cwd=sibling).stdout
    assert "hm-finalize-" not in primary_stash, f"primary stash leaked: {primary_stash!r}"
    assert "hm-finalize-" not in sibling_stash, f"sibling stash leaked: {sibling_stash!r}"

    # Both ref files cleaned
    assert not list((primary / ".claude").glob(".hm-finalize-stash-*"))
    assert not list((sibling / ".claude").glob(".hm-finalize-stash-*"))

    # Loop marker MUST be deleted post-pop (REVIEW round 2 P2: prior test
    # didn't assert this — the marker is the liveness signal; if leaked, the
    # next session's stale-ref check would mistakenly classify any future ref
    # files under this wt_name as fresh).
    marker = primary / ".claude" / f".hm-loop-{primary_wt.name}"
    assert not marker.is_file(), (
        f"loop marker must be deleted after all refs popped. marker={marker}"
    )


def test_multi_repo_untracked_harness_yaml_still_discoverable(
    tmp_path: Path,
) -> None:
    """REVIEW round 2 P1: untracked harness.yaml must NOT be swept into stash.

    Reproduces the production scenario where the user has run `/hm:make` but
    has not committed harness.yaml yet. Before the fix, `git stash push -u`
    would sweep the file, `_cli_post_commit_pop` would find harness.yaml gone,
    `_load_sibling_dirs` would return [], and sibling stashes would be
    permanently leaked.

    With the fix (`_HARNESS_ARTIFACT_PREFIXES` excludes harness.yaml from the
    dirty-trigger AND `git stash push --` excludes it from the stash itself),
    harness.yaml stays on disk through finalize and post-commit-pop can read
    sibling_repos.
    """
    # Set up primary + sibling WITHOUT committing harness.yaml in primary
    primary = tmp_path / "primary"
    sibling = tmp_path / "sibling"
    primary.mkdir()
    sibling.mkdir()
    for p in (primary, sibling):
        _git(["init", "-b", "main"], cwd=p)
        _git(["config", "user.email", "t@t"], cwd=p)
        _git(["config", "user.name", "t"], cwd=p)
        (p / "README.md").write_text(f"# {p.name}\n")
        (p / ".gitignore").write_text(
            ".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n"
        )
        _git(["add", "."], cwd=p)
        _git(["commit", "-m", "init"], cwd=p)

    # harness.yaml is written AFTER init commit — untracked from git's view
    (primary / ".claude").mkdir()
    rel_sibling = sibling.resolve().relative_to(tmp_path.resolve())
    (primary / ".claude" / "harness.yaml").write_text(f"sibling_repos:\n  - ../{rel_sibling}\n")

    # Sanity: yaml is untracked
    status = _git(["status", "--porcelain"], cwd=primary).stdout
    assert "?? .claude/" in status, f"yaml must be untracked. status: {status!r}"

    # Worktree + commits + sibling WIP
    wts = worktree.create("execute", primary, sibling_dirs=[sibling])
    primary_wt, sibling_wt = wts
    (primary_wt / "p.py").write_text("p\n")
    _git(["add", "."], cwd=primary_wt)
    _git(["commit", "-m", "p"], cwd=primary_wt)
    (sibling_wt / "s.py").write_text("s\n")
    _git(["add", "."], cwd=sibling_wt)
    _git(["commit", "-m", "s"], cwd=sibling_wt)

    # User WIP that DOES trigger stash (separate from harness.yaml)
    sibling_wip = "# sibling\n\nUNTRACKED-YAML SCENARIO WIP\n"
    (sibling / "README.md").write_text(sibling_wip)
    _git(["add", "README.md"], cwd=sibling)

    rc = worktree._cli_finalize([str(primary_wt), "stage-only"])
    assert rc == 0, f"finalize must succeed; got rc={rc}"

    # Commit + post-commit-pop. With the new design (sibling_bases embedded in
    # ref body), harness.yaml is irrelevant to pop-time discovery — sibling
    # bases are read from primary's ref file, NOT from yaml. So whether the
    # yaml is on disk or stashed doesn't affect correctness.
    _git(["commit", "-m", "wrap p"], cwd=primary)
    _git(["commit", "-m", "wrap s"], cwd=sibling)
    rc2 = worktree._cli_post_commit_pop([str(primary)])
    assert rc2 == 0, (
        "sibling discovery via ref-file body must work even when harness.yaml "
        "is in the stash — the chicken-and-egg deadlock is fixed by reading "
        "sibling_bases from the ref body, not from yaml on disk."
    )

    # Sibling stash drained
    assert (sibling / "README.md").read_text() == sibling_wip, (
        "sibling WIP must survive even with untracked harness.yaml"
    )


def test_validate_stash_ref_fields_edge_cases(tmp_path: Path) -> None:
    """REVIEW round 4 P2: direct unit coverage for _validate_stash_ref_fields
    rejection paths. Validator hardening is security-critical; this guards
    against regression of NUL/pipe/newline/symlink/non-absolute rejections.
    """
    # A valid baseline (all checks pass)
    marker = tmp_path / ".claude" / ".hm-loop-execute-test"
    marker.parent.mkdir(parents=True)
    marker.touch()
    valid: dict[str, str] = {
        "ref_sha": "a" * 40,
        "base": str(tmp_path),
        "session_marker": str(marker),
        "created_at": "2026-05-20T00:00:00+00:00",
    }
    assert worktree._validate_stash_ref_fields(valid) is not None, "baseline valid ref must pass"

    # Rejection table — each row mutates ONE field, expects None
    reject_cases: list[tuple[str, str, str]] = [
        ("ref_sha", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "uppercase hex"),
        ("ref_sha", "a" * 39, "wrong length"),
        ("base", "relative/path", "non-absolute"),
        ("base", f"{tmp_path}\x00inject", "NUL byte"),
        ("base", f"{tmp_path}|other", "pipe char"),
        ("base", f"{tmp_path}\ninject: /evil", "newline"),
        ("base", f"{tmp_path}/../escape", "dotdot segment"),
        ("session_marker", "/no/claude/in/path", "regex mismatch"),
        ("session_marker", f"{tmp_path}/.claude/.hm-loop-bad\nkey: val", "newline inject"),
        ("created_at", "", "missing"),
        ("created_at", "not-iso", "unparseable"),
        ("sibling_bases", "/foo|/bar\nINJECT", "newline in sibling token"),
        ("sibling_bases", f"{tmp_path}\x00", "NUL in sibling token"),
        ("base", "//foo/bar", "double-slash POSIX prefix"),
        ("session_marker", "//foo/.claude/.hm-loop-x", "double-slash marker"),
        ("sibling_bases", "//foo/bar", "double-slash in sibling token"),
        ("sibling_bases", f"{tmp_path}/sibling\nINJECT", "newline in sibling (re-check)"),
        ("base", f"{tmp_path}/./trick", "single-dot segment"),
        ("base", f"{tmp_path}\rinject", "CR character"),
    ]
    for field, bad_value, label in reject_cases:
        mutated = {**valid, field: bad_value}
        assert worktree._validate_stash_ref_fields(mutated) is None, (
            f"validator must REJECT {field}={bad_value!r} ({label})"
        )

    # Symlink rejection — requires real filesystem setup. `_is_safe_absolute_path`
    # rejects symlinks at both `base` and `session_marker` to prevent TOCTOU-style
    # swap attacks where a validated path is later resolved to an unintended
    # target. This row guarantees the predicate's symlink branch has coverage.
    real_target = tmp_path / "real_target"
    real_target.mkdir()
    base_symlink = tmp_path / "base_link"
    base_symlink.symlink_to(real_target)
    marker_target = tmp_path / "real_marker_target"
    marker_target.touch()
    marker_dir = tmp_path / ".claude"
    marker_symlink = marker_dir / ".hm-loop-symlinked"
    marker_symlink.symlink_to(marker_target)

    sym_base = {**valid, "base": str(base_symlink)}
    assert worktree._validate_stash_ref_fields(sym_base) is None, (
        "symlinked base must be rejected (TOCTOU-swap defense)"
    )
    sym_marker = {**valid, "session_marker": str(marker_symlink)}
    assert worktree._validate_stash_ref_fields(sym_marker) is None, (
        "symlinked session_marker must be rejected"
    )


def test_load_sibling_dirs_rejects_path_traversal(tmp_path: Path) -> None:
    """REVIEW round 2 P1: `_load_sibling_dirs` drops entries that don't
    resolve to a real git repo. Adversarial or typo'd entries like
    `../../etc/secrets` would otherwise become a base in `bases_to_scan`.
    """
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(["init", "-b", "main"], cwd=primary)
    _git(["config", "user.email", "t@t"], cwd=primary)
    _git(["config", "user.name", "t"], cwd=primary)
    (primary / ".claude").mkdir()

    # harness.yaml lists a real sibling AND an adversarial path
    real_sibling = tmp_path / "real-sibling"
    real_sibling.mkdir()
    _git(["init", "-b", "main"], cwd=real_sibling)

    yaml_path = primary / ".claude" / "harness.yaml"
    yaml_path.write_text(
        "sibling_repos:\n"
        f"  - ../{real_sibling.name}\n"
        "  - ../../etc/secrets\n"  # adversarial — doesn't exist OR not a git repo
        "  - /tmp\n"  # absolute non-git path
    )

    resolved = worktree._load_sibling_dirs(yaml_path, primary)
    # Only the real git repo survives — adversarial entries dropped with warning
    assert len(resolved) == 1, (
        f"path-traversal guard must drop non-git-repo entries. got: {resolved}"
    )
    assert resolved[0] == real_sibling.resolve()
