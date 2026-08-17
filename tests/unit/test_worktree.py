"""Unit tests for harness_maker.worktree (Phase 8 / Task 8.1).

Exercises real git operations inside tmp_path — the lifecycle is small enough
that mocking git would be more brittle than the real thing. Each test sets up
its own one-commit repo so they remain independent.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker import worktree


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(  # noqa: S603 — fixed args, no shell
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Initialize a real git repo with one commit on `main`."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(["init", "-b", "main"], cwd=r)
    _git(["config", "user.email", "test@example.com"], cwd=r)
    _git(["config", "user.name", "Test"], cwd=r)
    (r / "README.md").write_text("# repo\n")
    # Pre-track .gitignore so worktree.create() doesn't auto-create it as an
    # untracked file (which would otherwise appear in `git status --porcelain`
    # and trigger the stash isolation envelope on a "clean" base).
    (r / ".gitignore").write_text(".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n")
    _git(["add", "."], cwd=r)
    _git(["commit", "-m", "init"], cwd=r)
    return r


def test_create_returns_list_of_path(repo: Path) -> None:
    result = worktree.create("execute", repo)
    assert isinstance(result, list)
    assert len(result) == 1
    wt = result[0]
    assert wt.exists()
    assert wt.is_dir()
    assert wt.parent.name == worktree.WORKTREE_DIR_NAME
    assert wt.name.startswith("execute-")


def test_create_generates_unique_branch(repo: Path) -> None:
    wt = worktree.create("dev", repo)[0]
    cp = subprocess.run(  # noqa: S603
        ["git", "branch", "--list"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    branch = wt.name
    assert branch in cp.stdout


def test_cleanup_on_success_removes_directory(repo: Path) -> None:
    wt = worktree.create("execute", repo)[0]
    assert wt.exists()
    worktree.cleanup(wt, on_success=True)
    assert not wt.exists()


def test_cleanup_on_failure_preserves_dirty_worktree(repo: Path) -> None:
    """Non-force cleanup must leave a dirty worktree intact for inspection."""
    wt = worktree.create("execute", repo)[0]
    (wt / "scratch.txt").write_text("uncommitted\n")
    # Should not raise even though cleanup itself fails internally.
    worktree.cleanup(wt, on_success=False)
    # Worktree directory still present because git refused to remove dirty WT.
    assert wt.exists()


def test_merge_squash_brings_worktree_changes_into_base(repo: Path) -> None:
    wt = worktree.create("execute", repo)[0]
    # Make a commit inside the worktree.
    (wt / "feature.txt").write_text("feature\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "feature"], cwd=wt)
    # Merge back.
    worktree.merge(wt, strategy="squash")
    assert (repo / "feature.txt").exists()


def test_finalize_stage_only_captures_uncommitted_work(repo: Path) -> None:
    """Bug 2026-05-08: stage-only finalize used to silently lose uncommitted edits.

    The bug: `git merge --squash <branch>` only sees committed work; if the
    worktree had pending edits, `cleanup(force=True)` then deleted them.
    The fix: _capture_pending_in_worktree() makes a WIP commit on the worktree's
    branch first, so the merge picks the work up. This test exercises the path:
    - Make uncommitted edits in the worktree.
    - Run finalize stage-only.
    - Assert the uncommitted edits landed on `main` as staged changes (not lost).
    """
    wt = worktree.create("execute", repo)[0]
    # Uncommitted, unstaged edit (the lossy case).
    (wt / "feature.txt").write_text("uncommitted feature work\n")
    # Run finalize stage-only.
    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0, f"finalize returned {rc}"
    # Worktree dir must be cleaned up.
    assert not wt.exists()
    # The previously-uncommitted work must now be staged on `main`, not lost.
    on_main = repo / "feature.txt"
    assert on_main.exists(), "uncommitted feature.txt was lost by finalize"
    assert on_main.read_text() == "uncommitted feature work\n"
    # And the staging area should hold it (stage-only does not create the commit).
    diff_cached = subprocess.run(  # noqa: S603
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "feature.txt" in diff_cached.stdout


def test_finalize_success_captures_uncommitted_work(repo: Path) -> None:
    """Same fix verified on the `success` finalize path (auto-commit mode)."""
    wt = worktree.create("execute", repo)[0]
    (wt / "src.py").write_text("print('hi')\n")
    rc = worktree._cli_finalize([str(wt), "success"])
    assert rc == 0
    assert not wt.exists()
    # `success` mode auto-commits the squash-merge — work lands as a real commit.
    assert (repo / "src.py").exists()
    log = subprocess.run(  # noqa: S603
        ["git", "log", "--oneline", "-1"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "squash-merge worktree" in log.stdout


def test_finalize_fail_preserves_uncommitted_work(repo: Path) -> None:
    """`fail` finalize path must NOT auto-commit — uncommitted state stays for inspection."""
    wt = worktree.create("execute", repo)[0]
    (wt / "broken.py").write_text("# this code is wrong\n")
    rc = worktree._cli_finalize([str(wt), "fail"])
    # fail path returns 0 when cleanup succeeds; worktree dir is removed but
    # branch + uncommitted state is preserved on the branch ref via cleanup
    # behavior. The uncommitted file is intentionally left as evidence on disk
    # IF the cleanup keeps the worktree (non-force); since we use non-force on
    # fail, the dir stays.
    # The contract: NOT lost on main.
    assert not (repo / "broken.py").exists(), "fail mode should NOT propagate edits to main"
    # Per worktree.py:127-133 (cleanup with on_success=False), RuntimeError is
    # swallowed — the cleanup non-force path is allowed to fail when the worktree
    # is dirty, leaving the directory for inspection. _cli_finalize then returns 0.
    assert rc == 0


def test_finalize_success_clears_marker_fail_keeps_it(repo: Path) -> None:
    """ADR-003/006 policy: success → marker deleted (gate releases); fail → marker
    KEPT (gate continues protecting worktree until user finalizes successfully).

    Old policy (pre-ADR-006) cleared marker on every path — that was wrong
    because a dirty/failed finalize left the worktree alive but unprotected.
    """
    # Success path: create() writes .hm-loop-{wt.name}; successful finalize clears it.
    wt = worktree.create("execute", repo)[0]
    marker = repo / ".claude" / f".hm-loop-{wt.name}"
    assert marker.exists(), "create() must write per-session marker"
    (wt / "feature.txt").write_text("work\n")
    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0
    assert not marker.exists(), "marker must be cleared on stage-only success"

    # Fail path: marker is KEPT so gate continues protecting the surviving worktree.
    wt2 = worktree.create("execute", repo)[0]
    marker2 = repo / ".claude" / f".hm-loop-{wt2.name}"
    assert marker2.exists()
    rc = worktree._cli_finalize([str(wt2), "fail"])
    assert rc == 0
    assert marker2.exists(), "marker must be KEPT on fail path (gate still active)"


def test_cleanup_all_removes_every_worktree(repo: Path) -> None:
    wt1 = worktree.create("execute", repo)[0]
    # Force a different timestamp by switching minute is overkill; just create
    # a second worktree manually so we exercise the multi-removal path.
    wt2_path = repo / worktree.WORKTREE_DIR_NAME / "execute-manual"
    subprocess.run(  # noqa: S603
        ["git", "worktree", "add", "-b", "execute-manual", str(wt2_path)],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    assert wt1.exists()
    assert wt2_path.exists()
    count = worktree.cleanup_all(repo, force=True)
    assert count == 2
    assert not wt1.exists()
    assert not wt2_path.exists()


def test_cleanup_all_returns_zero_when_empty(repo: Path) -> None:
    assert worktree.cleanup_all(repo, force=True) == 0


def test_cli_cleanup_all_dispatch(repo: Path) -> None:
    """Regression (F50): cleanup_all was unreachable from main() — the disk
    cleanup defense could never fire. The `cleanup-all` subcommand must dispatch."""
    worktree.create("execute", repo)
    assert worktree.main(["cleanup-all", str(repo), "--force"]) == 0
    assert not list((repo / worktree.WORKTREE_DIR_NAME).glob("execute-*"))


def test_cli_create_emits_path_when_scope_includes_stage(repo: Path) -> None:
    """`python -m harness_maker.worktree create execute <repo>` returns the
    new worktree path on stdout when harness.yaml.worktree.scope contains
    'execute'. Used by stages/execute.md.j2 as deterministic dispatch."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute, plan]\n",
        encoding="utf-8",
    )
    rc = worktree.main(["create", "execute", str(repo)])
    assert rc == 0


def test_cli_create_parallel_sessions_get_independent_worktrees(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR-006: two create() calls from the project root (parallel sessions)
    must each get an independent worktree — not reuse the first one.

    Loop→sub-call idempotency is handled via path-based detection only
    (Signal 2): when the loop CDs into <WT> before dispatching sub-commands,
    the sub-command's pwd IS inside .worktrees/ and path detection returns it.
    """
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    rc1 = worktree.main(["create", "execute", str(repo)])
    wt1 = Path(capsys.readouterr().out.strip())
    assert rc1 == 0

    # Second session from project root → separate worktree (not reuse)
    rc2 = worktree.main(["create", "execute", str(repo)])
    wt2 = Path(capsys.readouterr().out.strip())
    assert rc2 == 0
    assert wt1 != wt2, "parallel sessions must NOT share a worktree"
    assert wt1.exists()
    assert wt2.exists()
    # Each session has its own marker file
    assert (repo / ".claude" / f".hm-loop-{wt1.name}").is_file()
    assert (repo / ".claude" / f".hm-loop-{wt2.name}").is_file()


def test_cli_create_idempotent_when_already_in_worktree(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When base_dir is already inside `.worktrees/<name>/...`, return that
    worktree path without creating a new one. Lets `/hm:loop` engage one
    worktree at the top and have nested standalone /hm:execute calls reuse
    it (PLAN per-loop worktree design)."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    # First call creates a worktree
    rc1 = worktree.main(["create", "execute", str(repo)])
    out1 = capsys.readouterr().out.strip()
    assert rc1 == 0
    wt_root = Path(out1)
    assert wt_root.is_dir()
    assert wt_root.parent.name == worktree.WORKTREE_DIR_NAME

    # Second call from the SAME worktree dir → idempotent: same path back
    rc2 = worktree.main(["create", "execute", str(wt_root)])
    out2 = capsys.readouterr().out.strip()
    assert rc2 == 0
    assert out2 == str(wt_root)
    # No nested worktree was created
    assert not (wt_root / worktree.WORKTREE_DIR_NAME).exists()


def test_cli_create_idempotent_from_subdir_of_worktree(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Idempotency works from arbitrary subdirs of the worktree root —
    `pwd` deep inside the loop's working tree must still resolve back to
    the worktree root, not create a new one."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    # Create the parent worktree first
    worktree.main(["create", "execute", str(repo)])
    wt_root = Path(capsys.readouterr().out.strip())
    sub = wt_root / "src" / "module"
    sub.mkdir(parents=True)

    # Call from deep subdir → still returns the worktree root
    rc2 = worktree.main(["create", "execute", str(sub)])
    out = capsys.readouterr().out.strip()
    assert rc2 == 0
    assert out == str(wt_root)


# ── Negative tests for false-positive idempotency (review finding #7) ──────


def test_cli_create_does_not_match_unrelated_dotworktrees_dir(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A directory literally named `.worktrees/foo` that ISN'T a real git
    worktree (no `.git` file/dir inside) must NOT short-circuit. Realistic
    case: another tool's storage at `~/.worktrees/...`, or a stale leftover.
    """
    fake = tmp_path / "outside-repo" / worktree.WORKTREE_DIR_NAME / "name"
    fake.mkdir(parents=True)
    # No .git inside — this is NOT a real worktree
    rc = worktree.main(["create", "execute", str(fake)])
    out = capsys.readouterr().out.strip()
    # Should fall through to scope check; with no harness.yaml at fake's
    # project root, scope check is False → empty stdout (no isolation,
    # NOT idempotent-return-fake-path).
    assert rc == 0
    assert out == ""


def test_cli_create_does_not_match_dotworktrees_as_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A regular FILE (not dir) named `.worktrees` somewhere in the path
    parts must not trigger idempotency. Edge case but the path-parts
    check shouldn't be naive about file-vs-dir."""
    # Construct an artificial path: `<tmp>/.worktrees/inner` where
    # .worktrees/inner exists as a real dir but the candidate `<tmp>/.worktrees`
    # parent is NOT a worktree (no .git). is_dir check on the candidate
    # plus .git probe both gate against this.
    base = tmp_path / worktree.WORKTREE_DIR_NAME / "inner"
    base.mkdir(parents=True)
    # No .git inside → must NOT short-circuit
    rc = worktree.main(["create", "execute", str(base)])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == ""


# ── Marker lifecycle (worktree_gate cooperation) ───────────────────────────


def test_cli_create_writes_loop_marker(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`worktree create` persists `.claude/.hm-loop-active` containing the
    new worktree path so `worktree_gate` can enforce <WT> scope on
    Write/Edit/MultiEdit during the loop."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    rc = worktree.main(["create", "execute", str(repo)])
    wt_path = capsys.readouterr().out.strip()
    assert rc == 0
    wt_name = Path(wt_path).name
    marker = repo / ".claude" / f".hm-loop-{wt_name}"
    assert marker.is_file(), "per-session marker must exist"
    assert wt_path in marker.read_text(encoding="utf-8")


def test_cli_create_appends_marker_to_gitignore(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Round H BLOCK 2 fix: marker file must be gitignored. Without this,
    a stale marker from a crashed loop could be committed and break every
    collaborator's gate against a non-existent worktree path."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    worktree.main(["create", "execute", str(repo)])
    capsys.readouterr()
    gitignore = repo / ".gitignore"
    assert gitignore.is_file()
    lines = [line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()]
    assert ".claude/.hm-loop-*" in lines


def test_cli_create_idempotent_gitignore_no_duplicate(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two consecutive `worktree create` (e.g. user re-runs /hm:loop) must
    not duplicate the .gitignore line."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    worktree.main(["create", "execute", str(repo)])
    wt = Path(capsys.readouterr().out.strip())
    worktree.main(["finalize", str(wt), "fail"])
    capsys.readouterr()
    worktree.main(["create", "execute", str(repo)])
    capsys.readouterr()
    gitignore = repo / ".gitignore"
    text = gitignore.read_text(encoding="utf-8")
    assert text.count(".claude/.hm-loop-*") == 1


def test_cli_create_preserves_existing_gitignore_content(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Existing .gitignore content (other patterns) must be preserved when
    we append the marker entry. No clobber, no reordering."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    (repo / ".gitignore").write_text(
        "# user gitignore\n*.pyc\n.env\n.claude/\n.worktrees/\n",
        encoding="utf-8",
    )
    # Phase 2 dirty-base guard would ABORT create on the unstaged .gitignore
    # modification; commit the gitignore overwrite so the test exercises
    # gitignore-append semantics (the actual contract under test), not
    # dirty-base guard interaction (covered separately in
    # test_worktree_dirty_base_guard.py).
    _git(["add", ".gitignore"], cwd=repo)
    _git(["commit", "-m", "test-fixture: rewrite gitignore"], cwd=repo)
    worktree.main(["create", "execute", str(repo)])
    capsys.readouterr()
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "# user gitignore" in text
    assert "*.pyc" in text
    assert ".env" in text
    # `_ensure_gitignore_entry` (2026-05-24) gained a subsumption check via
    # `git check-ignore` — when the entry is already covered by a broader
    # pattern (e.g. `.claude/` covers `.claude/.hm-loop-*`), no append. Both
    # outcomes satisfy the contract "marker file ends up gitignored".
    import subprocess

    proves_covered = subprocess.run(
        ["git", "check-ignore", "-q", "--", ".claude/.hm-loop-x"],
        cwd=str(repo),
        capture_output=True,
    )
    assert (
        ".claude/.hm-loop-*" in text
        or proves_covered.returncode == 0  # subsumed by .claude/ broader pattern
    )


def test_cli_create_no_marker_when_scope_off(
    repo: Path,
) -> None:
    """Scope check off → no worktree created → no marker (gate stays
    no-op so user can edit main freely)."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Side\nworktree:\n  scope: []\n",
        encoding="utf-8",
    )
    worktree.main(["create", "execute", str(repo)])
    # No .hm-loop-* files should exist (scope off → no worktree created)
    assert list((repo / ".claude").glob(".hm-loop-*")) == []


def test_cli_finalize_success_clears_marker(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """After successful finalize, marker is removed so worktree_gate stops
    blocking main edits."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    worktree.main(["create", "execute", str(repo)])
    wt_path = Path(capsys.readouterr().out.strip())
    (wt_path / "new.txt").write_text("ok\n")
    _git(["add", "."], cwd=wt_path)
    _git(["commit", "-m", "x"], cwd=wt_path)
    marker = repo / ".claude" / f".hm-loop-{wt_path.name}"
    assert marker.is_file()
    rc = worktree.main(["finalize", str(wt_path), "success"])
    assert rc == 0
    assert not marker.exists()


def test_cli_finalize_fail_keeps_marker(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR-003/006: fail path KEEPS the marker — gate continues protecting the
    worktree until user runs a successful finalize."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    worktree.main(["create", "execute", str(repo)])
    wt_path = Path(capsys.readouterr().out.strip())
    marker = repo / ".claude" / f".hm-loop-{wt_path.name}"
    assert marker.is_file()
    rc = worktree.main(["finalize", str(wt_path), "fail"])
    assert rc == 0
    assert marker.is_file(), "fail path must KEEP marker (gate stays active)"


def test_cli_finalize_does_not_clear_other_session_marker(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR-006: per-session markers — finalize wt_b deletes only its own marker,
    never wt_a's. Parallel sessions each own their own file."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    wt_a = worktree.create("execute", repo)[0]
    wt_b = worktree.create("execute", repo)[0]
    marker_a = repo / ".claude" / f".hm-loop-{wt_a.name}"
    marker_b = repo / ".claude" / f".hm-loop-{wt_b.name}"
    assert marker_a.is_file()
    assert marker_b.is_file()

    # Successful finalize of wt_b → deletes marker_b, marker_a untouched
    (wt_b / "f.txt").write_text("x\n")
    _git(["add", "."], cwd=wt_b)
    _git(["commit", "-m", "x"], cwd=wt_b)
    rc = worktree.main(["finalize", str(wt_b), "success"])
    assert rc == 0
    assert not marker_b.exists(), "finalize must delete its own session's marker"
    assert marker_a.is_file(), "finalize must NOT touch other session's marker"


def test_cli_create_picks_innermost_when_nested_dotworktrees(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nested `.worktrees/.worktrees/<name>` (pathological but possible)
    must resolve to the INNER worktree, not the outer false match. We walk
    right-to-left so the innermost real worktree wins."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    # Create a real worktree first via the API
    outer_wt = worktree.create("outer", repo)[0]
    # Manufacture a REAL nested git worktree inside the outer worktree's
    # `.worktrees/` directory. Using a real worktree (not a planted `.git`
    # file) is required since round 4 hardening: `_detect_existing_worktree`
    # now uses `git rev-parse --git-dir` (authoritative) instead of bare
    # `.git`-existence — which means planted regular files no longer pass.
    # This test still verifies innermost-wins; the path-walking logic is
    # unchanged, only the leaf gate is stricter.
    nested_parent = outer_wt / worktree.WORKTREE_DIR_NAME
    nested_parent.mkdir(parents=True, exist_ok=True)
    # Create a real worktree of the OUTER repo as the nested entry. Branch
    # name must differ from the outer's existing branches.
    nested_root = nested_parent / "inner"
    subprocess.run(
        ["git", "worktree", "add", "-b", "inner-branch", str(nested_root)],
        cwd=str(outer_wt),
        check=True,
        capture_output=True,
        text=True,
    )

    rc = worktree.main(["create", "execute", str(nested_root)])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    # Innermost wins: returned path is `nested_root`, not the outer worktree
    assert out == str(nested_root)


def test_cli_create_emits_empty_when_scope_excludes_stage(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scope check off → empty stdout, exit 0. Slash command treats empty
    string as 'no isolation needed, run in place'."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Side\nworktree:\n  scope: []\n",
        encoding="utf-8",
    )
    rc = worktree.main(["create", "execute", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() == ""


def test_cli_create_emits_empty_when_no_harness_yaml(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing harness.yaml → no-op (slash command runs in place). Defensive
    against fresh checkouts or non-harness projects."""
    rc = worktree.main(["create", "execute", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() == ""


def test_cli_create_handles_malformed_harness_yaml(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Malformed YAML → worktree_enabled catches YAMLError → returns False →
    CLI emits empty + exit 0. Never crashes the slash command."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [unclosed\n",  # syntax error
        encoding="utf-8",
    )
    rc = worktree.main(["create", "execute", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() == ""


def test_cli_create_handles_yaml_without_worktree_key(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """harness.yaml parses but lacks `worktree` key entirely → no isolation
    (the `not isinstance(wt, dict)` short-circuit). Hand-edited or partial
    yaml shouldn't break the slash command."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Side\nlocale: en\n",
        encoding="utf-8",
    )
    rc = worktree.main(["create", "execute", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() == ""


def test_create_collision_within_same_minute_retries_with_suffix(
    repo: Path,
) -> None:
    """Two create() calls within the same UTC minute share a base timestamp
    → second call appends `-1` suffix (PLAN-cursor-rootcause finding #3).
    Realistic for autoloop / fused workflows that re-enter execute fast."""
    wt1 = worktree.create("execute", repo)[0]
    wt2 = worktree.create("execute", repo)[0]
    assert wt1 != wt2
    assert wt1.exists()
    assert wt2.exists()


def test_cli_finalize_success_with_cleanup_failure_returns_1(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When cleanup() raises after a successful merge (e.g. locked file on
    Windows), _cli_finalize must surface via stderr + exit 1, not bare
    traceback. Honors the "never block" contract."""
    wt = worktree.create("execute", repo)[0]
    (wt / "new.txt").write_text("hi\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "x"], cwd=wt)

    def boom(*_a: object, **_kw: object) -> None:
        raise RuntimeError("cleanup failed: locked file")

    monkeypatch.setattr(worktree, "cleanup", boom)
    rc = worktree.main(["finalize", str(wt), "success"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "cleanup failed" in err
    assert str(wt) in err


def test_cli_finalize_success_merges_and_cleans(repo: Path) -> None:
    """finalize success → squash merge + cleanup --force. No worktree dir
    remains; the change is on the base branch."""
    wt = worktree.create("execute", repo)[0]
    (wt / "new.txt").write_text("hi\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "add new.txt"], cwd=wt)

    rc = worktree.main(["finalize", str(wt), "success"])
    assert rc == 0
    assert not wt.exists()
    assert (repo / "new.txt").exists()  # squash-merged into base


def test_cli_finalize_fail_preserves_worktree(repo: Path) -> None:
    """finalize fail → no merge, cleanup non-force. Dirty worktree stays
    so the user can inspect (parity with cleanup(on_success=False))."""
    wt = worktree.create("execute", repo)[0]
    (wt / "dirty.txt").write_text("uncommitted\n")  # unstaged change

    rc = worktree.main(["finalize", str(wt), "fail"])
    # cleanup non-force errors on dirty worktree but main() must still exit 0
    # (the docstring contract: never block; preserve evidence).
    assert rc == 0
    assert wt.exists()  # preserved for inspection


def test_cli_finalize_missing_path_is_noop(repo: Path) -> None:
    """If create() returned empty (scope off) and the slash command still
    pipes finalize through, it must no-op rather than error."""
    rc = worktree.main(["finalize", str(repo / ".worktrees" / "ghost"), "success"])
    assert rc == 0


def test_cli_unknown_subcommand_returns_error() -> None:
    rc = worktree.main(["frobnicate"])
    assert rc == 2


def test_cli_create_arg_count_validation() -> None:
    rc = worktree.main(["create"])
    assert rc == 2


def test_cli_finalize_invalid_status() -> None:
    rc = worktree.main(["finalize", "/tmp/whatever", "maybe"])
    assert rc == 2


def test_create_inside_nonrepo_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="git command failed"):
        worktree.create("execute", tmp_path)


def _branch_exists(branch: str, repo: Path) -> bool:
    cp = subprocess.run(  # noqa: S603 — fixed args, no shell
        ["git", "branch", "--list", branch],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    return branch in cp.stdout


def test_prune_sweeps_squash_merged_orphan_branch(repo: Path) -> None:
    """P1: an orphan branch (worktree dir gone) whose work is in HEAD — tip is
    NOT a HEAD ancestor (squash case), but all tip blobs ARE in HEAD — is swept."""
    import shutil

    wt = worktree.create("execute", repo)[0]
    branch = wt.name
    (wt / "feat.txt").write_text("feature\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "wip(execute): feature"], cwd=wt)
    # Model squash-merge: the SAME content lands in base HEAD independently of the
    # branch, so the branch tip is not a HEAD ancestor yet every tip blob is in HEAD.
    (repo / "feat.txt").write_text("feature\n")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-m", "land feature (squash-equiv)"], cwd=repo)
    shutil.rmtree(wt)
    _git(["worktree", "prune"], cwd=repo)
    assert _branch_exists(branch, repo)  # leaked

    report = worktree.prune_stale(repo)
    assert not _branch_exists(branch, repo), "squash-merged orphan branch must be swept"
    assert branch in report.removed_branches


def test_prune_preserves_orphan_with_unmerged_content(repo: Path) -> None:
    """P1 (biased-to-preserve): an orphan branch whose content is NOT in HEAD is
    preserved + warned, never deleted."""
    import shutil

    wt = worktree.create("execute", repo)[0]
    branch = wt.name
    (wt / "unmerged.txt").write_text("only on the branch\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "wip(execute): unmerged work"], cwd=wt)
    # Do NOT land the content in HEAD. Orphan the worktree.
    shutil.rmtree(wt)
    _git(["worktree", "prune"], cwd=repo)

    report = worktree.prune_stale(repo)
    assert _branch_exists(branch, repo), "orphan with unmerged content must be preserved"
    assert any(branch == b for b, _hint in report.preserved_branches)
    assert any(branch in w for w in report.warnings)


def test_prune_does_not_sweep_live_worktree_branch(repo: Path) -> None:
    """P1: a branch whose worktree dir is still present (live session) is never
    swept — even when its content IS in HEAD, so only the dir-present check
    (not the content-gate) is what holds it back."""
    wt = worktree.create("execute", repo)[0]
    branch = wt.name
    # Land identical content in HEAD so the content-gate WOULD sweep — proving
    # the dir-present skip is the thing preserving the branch, not the gate.
    (wt / "feat.txt").write_text("feature\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "wip(execute): feature"], cwd=wt)
    (repo / "feat.txt").write_text("feature\n")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-m", "land feature"], cwd=repo)
    assert wt.exists()  # live — dir present
    report = worktree.prune_stale(repo)
    assert _branch_exists(branch, repo), "live worktree's branch must not be swept"
    assert branch not in report.removed_branches


# ── P2: merge-fence boundary widening (PLAN-p6-p7-worktree-finalize ADR-003) ──
#
# The fence must wrap EXACTLY {_stash_base_dirty, staged_before snapshot,
# merge()} — staged_before strictly AFTER the stash — with handed_off /
# ref-write / cleanup / both pop paths pinned OUTSIDE. _capture_pending_in_worktree
# is worktree-side (not base-repo), so it stays OUTSIDE the base-repo fence.


def _make_base_dirty(repo: Path, name: str = "user_dirt.txt", body: str = "user wip\n") -> Path:
    """Stage a non-harness user file in base so `_stash_base_dirty` actually stashes."""
    p = repo / name
    p.write_text(body)
    _git(["add", name], cwd=repo)
    return p


def test_finalize_stash_runs_inside_merge_fence(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RED gate for ADR-003: `_stash_base_dirty` must execute INSIDE the merge
    fence (currently it runs before the fence is ever acquired). Records the
    enter/stash/exit order via spies that delegate to the real impls."""
    wt = worktree.create("execute", repo)[0]
    (wt / "wt_file.txt").write_text("worktree work\n")
    _make_base_dirty(repo)  # base dirty → stash path engages

    events: list[str] = []
    real_fence = worktree._acquire_merge_fence
    real_stash = worktree._stash_base_dirty

    @contextlib.contextmanager
    def rec_fence(base: Path, timeout: float = 60.0):  # type: ignore[no-untyped-def]
        events.append("fence-enter")
        try:
            with real_fence(base, timeout=timeout):
                yield
        finally:
            events.append("fence-exit")

    def rec_stash(base: Path, wt_name: str) -> str | None:
        events.append("stash")
        return real_stash(base, wt_name)

    monkeypatch.setattr(worktree, "_acquire_merge_fence", rec_fence)
    monkeypatch.setattr(worktree, "_stash_base_dirty", rec_stash)

    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0, f"finalize rc={rc}, events={events}"
    assert "fence-enter" in events, f"stash must run inside the fence; got {events}"
    assert "stash" in events, f"stash must run inside the fence; got {events}"
    i_enter = events.index("fence-enter")
    i_stash = events.index("stash")
    i_exit = events.index("fence-exit")
    assert i_enter < i_stash, f"stash must run after the fence is entered; got {events}"
    assert i_stash < i_exit, f"stash must run before the fence exits; got {events}"


def test_finalize_releases_fence_on_stash_failure(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-003: a `_stash_base_dirty` that raises INSIDE the fence → finalize
    returns 1 AND the fence is released (context-manager finally), so a
    subsequent acquisition is not blocked."""
    wt = worktree.create("execute", repo)[0]
    (wt / "wt_file.txt").write_text("worktree work\n")
    _make_base_dirty(repo)

    events: list[str] = []
    real_fence = worktree._acquire_merge_fence

    @contextlib.contextmanager
    def rec_fence(base: Path, timeout: float = 60.0):  # type: ignore[no-untyped-def]
        events.append("fence-enter")
        try:
            with real_fence(base, timeout=timeout):
                yield
        finally:
            events.append("fence-exit")

    def boom_stash(base: Path, wt_name: str) -> str | None:
        events.append("stash-raise")
        raise RuntimeError("simulated stash failure")

    monkeypatch.setattr(worktree, "_acquire_merge_fence", rec_fence)
    monkeypatch.setattr(worktree, "_stash_base_dirty", boom_stash)

    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 1, f"stash failure must return 1; events={events}"
    # The raise happened inside the fence, and the fence still released.
    assert "fence-enter" in events, f"stash must raise inside the fence; got {events}"
    i_enter = events.index("fence-enter")
    i_raise = events.index("stash-raise")
    i_exit = events.index("fence-exit")
    assert i_enter < i_raise, f"stash must raise after the fence is entered; got {events}"
    assert i_raise < i_exit, f"fence must exit (release) after the stash raises; got {events}"

    # No leaked lock: the REAL fence acquires within a short timeout.
    monkeypatch.setattr(worktree, "_acquire_merge_fence", real_fence)
    with real_fence(repo, timeout=5.0):
        pass


def test_finalize_scope_guard_contamination_unchanged(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-003 ordering invariant: with `staged_before` captured AFTER the
    stash, a dirty-base stage-only finalize introduces NO scope-guard
    contamination — pre-existing user dirt is stashed out, the merge only
    stages the worktree's own file."""
    wt = worktree.create("execute", repo)[0]
    (wt / "wt_only.txt").write_text("worktree-only change\n")
    _make_base_dirty(repo, name="pre_existing.txt")  # pre-existing staged user content

    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "scope-guard violation" not in err, f"unexpected contamination flagged:\n{err}"


def test_finalize_stage_only_deferred_pop_handoff_unchanged(repo: Path) -> None:
    """ADR-003 pinned lower boundary: stage-only with a dirty base still writes
    the `.hm-finalize-stash-*` ref file, sets handed_off=True, and the finally
    does NOT pop — the user's dirt stays stashed for post-commit-pop, NOT
    restored into the index on top of the squash."""
    wt = worktree.create("execute", repo)[0]
    (wt / "wt_file.txt").write_text("worktree work\n")
    _make_base_dirty(repo, name="deferred_dirt.txt", body="defer me\n")

    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0
    # Ref file written (handoff to post-commit-pop).
    refs = list((repo / ".claude").glob(".hm-finalize-stash-execute-*"))
    assert refs, "stage-only with dirty base must write a finalize-stash ref file"
    # Deferred, NOT popped: the user dirt is not restored into the working tree.
    assert not (repo / "deferred_dirt.txt").exists(), (
        "stage-only must NOT pop the base stash in the finally (deferred to post-commit-pop)"
    )
    # And it survives in the stash list for later restoration.
    listing = subprocess.run(  # noqa: S603
        ["git", "stash", "list"], cwd=str(repo), check=True, capture_output=True, text=True
    )
    assert "execute-" in listing.stdout, "the deferred stash must remain in the stash list"


def test_finalize_fence_boundary_ordering(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-003 full boundary pin: the fence wraps EXACTLY {stash, staged_before
    snapshot, merge} with `staged_before` STRICTLY AFTER the stash, while
    `_write_stash_ref_file` (handoff) and `cleanup()` run STRICTLY AFTER the
    fence releases (the pinned lower boundary). Records the execution order of
    each named step and asserts the full ordering."""
    wt = worktree.create("execute", repo)[0]
    (wt / "wt_file.txt").write_text("worktree work\n")
    _make_base_dirty(repo)  # dirty base → stash + ref-write handoff engage

    events: list[str] = []
    real_fence = worktree._acquire_merge_fence
    real_stash = worktree._stash_base_dirty
    real_snapshot = worktree._snapshot_staged_paths
    real_refwrite = worktree._write_stash_ref_file
    real_cleanup = worktree.cleanup

    @contextlib.contextmanager
    def rec_fence(base: Path, timeout: float = 60.0):  # type: ignore[no-untyped-def]
        events.append("fence-enter")
        try:
            with real_fence(base, timeout=timeout):
                yield
        finally:
            events.append("fence-exit")

    def rec_stash(b: Path, wt_name: str) -> str | None:
        events.append("stash")
        return real_stash(b, wt_name)

    def rec_snapshot(b: Path) -> set[str]:
        events.append("snapshot")
        return real_snapshot(b)

    def rec_refwrite(*a: Any, **k: Any) -> None:
        events.append("ref-write")
        real_refwrite(*a, **k)

    def rec_cleanup(*a: object, **k: object) -> None:
        events.append("cleanup")
        return real_cleanup(*a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(worktree, "_acquire_merge_fence", rec_fence)
    monkeypatch.setattr(worktree, "_stash_base_dirty", rec_stash)
    monkeypatch.setattr(worktree, "_snapshot_staged_paths", rec_snapshot)
    monkeypatch.setattr(worktree, "_write_stash_ref_file", rec_refwrite)
    monkeypatch.setattr(worktree, "cleanup", rec_cleanup)

    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0, f"finalize rc={rc}, events={events}"

    steps = ("fence-enter", "stash", "snapshot", "fence-exit", "ref-write", "cleanup")
    for step in steps:
        assert step in events, f"missing {step}; got {events}"
    i = {s: events.index(s) for s in steps}
    # Upper boundary + staged_before strictly after stash + both inside the fence:
    assert i["fence-enter"] < i["stash"], events
    assert i["stash"] < i["snapshot"], events  # staged_before STRICTLY after stash
    assert i["snapshot"] < i["fence-exit"], events  # snapshot inside the fence
    # Pinned LOWER boundary: handoff + cleanup run AFTER the fence releases:
    assert i["fence-exit"] < i["ref-write"], events
    assert i["fence-exit"] < i["cleanup"], events


def test_finalize_success_mode_conflict_resets_index_before_pop(repo: Path) -> None:
    """CR1 (PLAN-p6-p7-worktree-finalize REVIEW): a success-mode (auto_commit)
    finalize whose squash-merge CONFLICTS must reset the conflicted index to HEAD
    before restoring the base stash — otherwise the stash pop runs over conflict
    markers. The rollback reset must fire on ANY failure (wt_rc != 0), not only
    the stage-only path (the old `if not auto_commit` guard skipped it here)."""
    # base: a tracked file the worktree and base will both diverge.
    (repo / "shared.txt").write_text("base\n")
    _git(["add", "shared.txt"], cwd=repo)
    _git(["commit", "-m", "add shared"], cwd=repo)
    # worktree changes shared.txt and commits.
    wt = worktree.create("execute", repo)[0]
    (wt / "shared.txt").write_text("worktree\n")
    _git(["add", "shared.txt"], cwd=wt)
    _git(["commit", "-m", "wt change"], cwd=wt)
    # base HEAD diverges the SAME file → the squash merge will conflict.
    (repo / "shared.txt").write_text("base-changed\n")
    _git(["add", "shared.txt"], cwd=repo)
    _git(["commit", "-m", "base change"], cwd=repo)
    # base dirty (untracked) so the stash path engages and the rollback pop fires.
    (repo / "dirt.txt").write_text("user dirt\n")

    rc = worktree._cli_finalize([str(wt), "success"])
    assert rc != 0, "a conflicting success-mode finalize must fail"
    # The conflicted index/working tree must have been reset to HEAD before the
    # stash pop — no leftover conflict markers, content back at HEAD.
    shared = (repo / "shared.txt").read_text()
    assert "<<<<<<<" not in shared, f"conflict markers left in base (index not reset): {shared!r}"
    assert shared == "base-changed\n", f"base shared.txt not restored to HEAD: {shared!r}"


# ── P3: safe polish (PLAN-p6-p7-worktree-finalize ADR-001 non-defense scope) ──


def test_porcelain_path_helper() -> None:
    """P3: a single `_porcelain_path(line)` extracts the path from a porcelain v1
    status line — handling the 2-char XY status, rename `old -> new` (RHS), and
    git's quote-wrapping for special chars. Replaces 3 divergent inline copies."""
    assert worktree._porcelain_path("?? foo.txt") == "foo.txt"
    assert worktree._porcelain_path(" M src/a.py") == "src/a.py"
    assert worktree._porcelain_path("A  staged.py") == "staged.py"
    # Rename: take the destination (right of the arrow), stripped.
    assert worktree._porcelain_path("R  old.py -> new.py") == "new.py"
    # Quote-wrapped path (git adds quotes for spaces/special chars).
    assert worktree._porcelain_path('?? "a b.txt"') == "a b.txt"
    assert worktree._porcelain_path('R  "o ld.py" -> "n ew.py"') == "n ew.py"
    # Too-short / empty → None (no path).
    assert worktree._porcelain_path("XY") is None
    assert worktree._porcelain_path("") is None


def test_list_user_dirty_files_routes_through_porcelain_helper(repo: Path) -> None:
    """P3: `_list_user_dirty_files` (previously did a bare `line[3:].strip()`,
    NO rename handling) now routes through `_porcelain_path`, so a staged rename
    of a USER file is listed as the destination path, not the raw `old -> new`."""
    (repo / "orig.py").write_text("x\n")
    _git(["add", "orig.py"], cwd=repo)
    _git(["commit", "-m", "add orig"], cwd=repo)
    _git(["mv", "orig.py", "renamed.py"], cwd=repo)  # staged rename → "R  orig.py -> renamed.py"
    dirty = worktree._list_user_dirty_files(repo)
    assert dirty == ["renamed.py"], f"rename must list the destination path only, got {dirty}"


def test_ensure_gitignore_batches_check_ignore(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """P3: `_ensure_harness_gitignore` must invoke `git check-ignore` ONCE
    (batched via --stdin), not once per churn pattern. Pre-seed a broad
    `.claude/` ignore so the `.claude/*` churn patterns are subsumed — the case
    that, in the per-entry loop, fired a check-ignore subprocess for each."""
    (repo / ".gitignore").write_text(
        ".claude/\nwork-docs/loop-context/\nwork-docs/p5-batch-state.yaml\n"
    )
    check_ignore_calls: list[list[str]] = []
    real_run = subprocess.run

    def counting_run(args: object, *a: object, **k: object) -> object:
        if isinstance(args, (list, tuple)) and "check-ignore" in args:
            check_ignore_calls.append(list(args))
        return real_run(args, *a, **k)  # type: ignore[call-overload]

    # String target, not `setattr(subprocess, ...)`: this is a SPY whose assertion can pass
    # vacuously (zero recorded calls satisfies it). Patching the bare stdlib module still
    # works if `worktree` stopped importing it, so the spy would record nothing and the test
    # would go green on a module it no longer observes. The dotted form raises instead.
    monkeypatch.setattr("harness_maker.worktree.subprocess.run", counting_run)
    worktree._ensure_harness_gitignore(repo)
    # RED-now lands at 8 (the 10 churn patterns minus the 2 work-docs lines this
    # fixture seeds as exact matches → short-circuited before check-ignore). The
    # broad `.claude/` seed makes the `.claude/*` patterns genuine subsumption
    # candidates, so exactly ONE batched call is the correct target.
    assert len(check_ignore_calls) == 1, (
        f"check-ignore must be batched into ONE call; got {len(check_ignore_calls)}: "
        f"{check_ignore_calls}"
    )


def test_ensure_gitignore_absent_creates_file_and_batches(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P3: when `.gitignore` is ABSENT, `_ensure_harness_gitignore` creates it
    with the churn patterns AND still batches check-ignore (≤1 call) — the old
    per-entry loop created the file then fired a check-ignore per remaining
    pattern."""
    gi = repo / ".gitignore"
    gi.unlink(missing_ok=True)  # the `repo` fixture pre-creates one — exercise the absent branch
    check_ignore_calls: list[list[str]] = []
    real_run = subprocess.run

    def counting_run(args: object, *a: object, **k: object) -> object:
        if isinstance(args, (list, tuple)) and "check-ignore" in args:
            check_ignore_calls.append(list(args))
        return real_run(args, *a, **k)  # type: ignore[call-overload]

    # String target, not `setattr(subprocess, ...)`: this is a SPY whose assertion can pass
    # vacuously (zero recorded calls satisfies it). Patching the bare stdlib module still
    # works if `worktree` stopped importing it, so the spy would record nothing and the test
    # would go green on a module it no longer observes. The dotted form raises instead.
    monkeypatch.setattr("harness_maker.worktree.subprocess.run", counting_run)
    worktree._ensure_harness_gitignore(repo)
    assert gi.is_file(), ".gitignore must be created when absent"
    content = gi.read_text()
    assert ".claude/observability/" in content, f"churn patterns not written: {content!r}"
    assert len(check_ignore_calls) <= 1, (
        f"check-ignore must be batched (≤1), got {len(check_ignore_calls)}: {check_ignore_calls}"
    )


# ── CR2 / CN1 / CN2 follow-ups (PLAN-p6-p7-worktree-finalize REVIEW) ──────────


def test_match_stash_sha_finds_message_substring() -> None:
    """CR2: `_match_stash_sha` finds the stash by its (UUID-bearing) message
    appearing ANYWHERE in git's `%gs` subject — so a format quirk (e.g. a
    trailing file-count) no longer makes `_stash_base_dirty` raise + orphan the
    just-pushed stash. The 32-hex UUID in the message keeps substring-match
    collision-safe."""
    sha = "a" * 40
    msg = "hm-finalize-execute-abc123-0123456789abcdef0123456789abcdef"
    # Plain `On <branch>: <msg>` form.
    assert worktree._match_stash_sha(f"{sha} On main: {msg}", msg) == sha
    # Bare-message form (some git versions).
    assert worktree._match_stash_sha(f"{sha} {msg}", msg) == sha
    # Quirk: trailing extra after the message — the OLD endswith/== match missed
    # this and raised (orphaning the stash); substring-match finds it.
    assert worktree._match_stash_sha(f"{sha} On main: {msg} (2 files)", msg) == sha
    # Genuinely absent → None (nothing to orphan; caller raises correctly).
    assert worktree._match_stash_sha(f"{sha} On main: some-other-stash", msg) is None
    assert worktree._match_stash_sha("", msg) is None


def test_finalize_merge_fence_timeout_covers_stash_hold(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CN1: the merge fence's acquire-timeout must be >= the worst-case time the
    critical section can HOLD it. Since the section now includes
    `_stash_base_dirty` (`git stash push -u`, timeout `_GIT_TIMEOUT_LONG`=300s),
    a 60s acquire budget would spuriously time out a 2nd parallel finalize."""
    wt = worktree.create("execute", repo)[0]
    (wt / "f.txt").write_text("x\n")
    timeouts: list[float] = []
    real_fence = worktree._acquire_merge_fence

    @contextlib.contextmanager
    def rec(base: Path, timeout: float = 60.0):  # type: ignore[no-untyped-def]
        timeouts.append(timeout)
        with real_fence(base, timeout=timeout):
            yield

    monkeypatch.setattr(worktree, "_acquire_merge_fence", rec)
    worktree._cli_finalize([str(wt), "stage-only"])
    assert timeouts, "merge fence was never acquired"
    assert all(t >= worktree._GIT_TIMEOUT_LONG for t in timeouts), (
        f"fence acquire-timeout must cover the {worktree._GIT_TIMEOUT_LONG}s stash hold; "
        f"got {timeouts}"
    )


def test_finalize_success_pop_runs_inside_fence(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CN2: the base stash pop (`_restore_base_dirty`) must run INSIDE a merge
    fence so two parallel finalizes don't race on the shared base stash/index.
    Currently the success-mode pop runs after the merge fence has released."""
    wt = worktree.create("execute", repo)[0]
    (wt / "f.txt").write_text("x\n")
    # base dirty so a stash is pushed → a pop happens in success mode.
    (repo / "dirt.txt").write_text("user dirt\n")

    events: list[str] = []
    real_fence = worktree._acquire_merge_fence
    real_restore = worktree._restore_base_dirty

    @contextlib.contextmanager
    def rec_fence(base: Path, timeout: float = 60.0):  # type: ignore[no-untyped-def]
        events.append("fence-enter")
        try:
            with real_fence(base, timeout=timeout):
                yield
        finally:
            events.append("fence-exit")

    def rec_restore(base: Path, ref: str) -> tuple[bool, str, list[Path]]:
        events.append("pop")
        return real_restore(base, ref)

    monkeypatch.setattr(worktree, "_acquire_merge_fence", rec_fence)
    monkeypatch.setattr(worktree, "_restore_base_dirty", rec_restore)

    rc = worktree._cli_finalize([str(wt), "success"])
    assert rc == 0, f"finalize rc={rc}, events={events}"
    assert "pop" in events, f"no base stash pop happened; events={events}"
    i = events.index("pop")
    assert i > 0, f"pop must be preceded by a fence-enter; events={events}"
    assert events[i - 1] == "fence-enter", (
        f"pop must be immediately inside a fence (fence-enter before it); events={events}"
    )
    assert i + 1 < len(events), f"the pop's fence must release after it; events={events}"
    assert events[i + 1] == "fence-exit", (
        f"the pop's fence must release right after it; events={events}"
    )
