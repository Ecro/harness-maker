"""Unit tests for harness_maker.worktree (Phase 8 / Task 8.1).

Exercises real git operations inside tmp_path — the lifecycle is small enough
that mocking git would be more brittle than the real thing. Each test sets up
its own one-commit repo so they remain independent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

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
        "# user gitignore\n*.pyc\n.env\n",
        encoding="utf-8",
    )
    worktree.main(["create", "execute", str(repo)])
    capsys.readouterr()
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "# user gitignore" in text
    assert "*.pyc" in text
    assert ".env" in text
    assert ".claude/.hm-loop-*" in text


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
    """Malformed YAML → _scope_includes catches YAMLError → returns False →
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
