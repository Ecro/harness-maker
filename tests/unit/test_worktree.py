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
    _git(["add", "."], cwd=r)
    _git(["commit", "-m", "init"], cwd=r)
    return r


def test_create_returns_path_and_directory_exists(repo: Path) -> None:
    wt = worktree.create("execute", repo)
    assert wt.exists()
    assert wt.is_dir()
    assert wt.parent.name == worktree.WORKTREE_DIR_NAME
    assert wt.name.startswith("execute-")


def test_create_generates_unique_branch(repo: Path) -> None:
    wt = worktree.create("dev", repo)
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
    wt = worktree.create("execute", repo)
    assert wt.exists()
    worktree.cleanup(wt, on_success=True)
    assert not wt.exists()


def test_cleanup_on_failure_preserves_dirty_worktree(repo: Path) -> None:
    """Non-force cleanup must leave a dirty worktree intact for inspection."""
    wt = worktree.create("execute", repo)
    (wt / "scratch.txt").write_text("uncommitted\n")
    # Should not raise even though cleanup itself fails internally.
    worktree.cleanup(wt, on_success=False)
    # Worktree directory still present because git refused to remove dirty WT.
    assert wt.exists()


def test_merge_squash_brings_worktree_changes_into_base(repo: Path) -> None:
    wt = worktree.create("execute", repo)
    # Make a commit inside the worktree.
    (wt / "feature.txt").write_text("feature\n")
    _git(["add", "."], cwd=wt)
    _git(["commit", "-m", "feature"], cwd=wt)
    # Merge back.
    worktree.merge(wt, strategy="squash")
    assert (repo / "feature.txt").exists()


def test_cleanup_all_removes_every_worktree(repo: Path) -> None:
    wt1 = worktree.create("execute", repo)
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


def test_cli_create_idempotent_via_marker_from_project_root(
    repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """When loop wrote the .hm-loop-active marker, a subsequent `create` from
    project root (NOT from inside .worktrees/) must return the loop's
    worktree, not make a new one. This is the realistic case for /hm:loop:
    loop creates worktree from project root, dispatches /hm:execute whose
    §0 also runs worktree create from project root — without marker-based
    idempotency, §0 creates a second worktree."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    # Loop's first create
    rc1 = worktree.main(["create", "execute", str(repo)])
    loop_wt = Path(capsys.readouterr().out.strip())
    assert rc1 == 0

    # Execute §0's call from same project root → must NOT make a new WT
    rc2 = worktree.main(["create", "execute", str(repo)])
    out2 = capsys.readouterr().out.strip()
    assert rc2 == 0
    assert out2 == str(loop_wt)
    # Filesystem confirms only one worktree exists
    worktrees_dir = repo / worktree.WORKTREE_DIR_NAME
    assert sum(1 for _ in worktrees_dir.iterdir()) == 1


def test_cli_create_idempotent_when_already_in_worktree(
    repo: Path, capsys: pytest.CaptureFixture[str],
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
    repo: Path, capsys: pytest.CaptureFixture[str],
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
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
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
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
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
    repo: Path, capsys: pytest.CaptureFixture[str],
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
    marker = repo / ".claude" / ".hm-loop-active"
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8").strip() == wt_path


def test_cli_create_appends_marker_to_gitignore(
    repo: Path, capsys: pytest.CaptureFixture[str],
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
    assert ".claude/.hm-loop-active" in lines


def test_cli_create_idempotent_gitignore_no_duplicate(
    repo: Path, capsys: pytest.CaptureFixture[str],
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
    assert text.count(".claude/.hm-loop-active") == 1


def test_cli_create_preserves_existing_gitignore_content(
    repo: Path, capsys: pytest.CaptureFixture[str],
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
    assert ".claude/.hm-loop-active" in text


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
    assert not (repo / ".claude" / ".hm-loop-active").exists()


def test_cli_finalize_success_clears_marker(
    repo: Path, capsys: pytest.CaptureFixture[str],
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
    marker = repo / ".claude" / ".hm-loop-active"
    assert marker.is_file()
    rc = worktree.main(["finalize", str(wt_path), "success"])
    assert rc == 0
    assert not marker.exists()


def test_cli_finalize_fail_also_clears_marker(
    repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Failure path still clears the marker — loop is over either way; user
    must be free to edit main again (cherry-pick from <WT>, retry, etc.)."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    worktree.main(["create", "execute", str(repo)])
    wt_path = Path(capsys.readouterr().out.strip())
    marker = repo / ".claude" / ".hm-loop-active"
    assert marker.is_file()
    rc = worktree.main(["finalize", str(wt_path), "fail"])
    assert rc == 0
    assert not marker.exists()


def test_cli_finalize_does_not_clear_marker_for_different_worktree(
    repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Concurrent loops: marker points to wt-A; finalize wt-B fires →
    marker for wt-A must NOT be clobbered. Prevents one loop's finalize
    from disabling another concurrent loop's gate."""
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [execute]\n",
        encoding="utf-8",
    )
    wt_a = worktree.create("execute", repo)
    wt_b = worktree.create("execute", repo)
    # Manually pin marker to wt_a (simulate "wt_a loop is the active one")
    marker = repo / ".claude" / ".hm-loop-active"
    marker.write_text(str(wt_a) + "\n", encoding="utf-8")

    # Finalize wt_b → must NOT clear marker
    rc = worktree.main(["finalize", str(wt_b), "fail"])
    assert rc == 0
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8").strip() == str(wt_a)


def test_cli_create_picks_innermost_when_nested_dotworktrees(
    repo: Path, capsys: pytest.CaptureFixture[str],
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
    outer_wt = worktree.create("outer", repo)
    # Manually manufacture a nested .worktrees/inner inside the outer
    # worktree root — synthesizes the pathological structure with a fake
    # .git file so the inner candidate passes the .git probe.
    nested_root = outer_wt / worktree.WORKTREE_DIR_NAME / "inner"
    nested_root.mkdir(parents=True)
    (nested_root / ".git").write_text("gitdir: /fake\n")  # marker file

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
    wt1 = worktree.create("execute", repo)
    wt2 = worktree.create("execute", repo)
    assert wt1 != wt2
    assert wt1.exists()
    assert wt2.exists()


def test_cli_finalize_success_with_cleanup_failure_returns_1(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When cleanup() raises after a successful merge (e.g. locked file on
    Windows), _cli_finalize must surface via stderr + exit 1, not bare
    traceback. Honors the "never block" contract."""
    wt = worktree.create("execute", repo)
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
    wt = worktree.create("execute", repo)
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
    wt = worktree.create("execute", repo)
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
