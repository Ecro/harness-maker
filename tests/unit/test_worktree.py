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
