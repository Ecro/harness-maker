"""Tests for multi-repo worktree support (Phase 2 / PLAN-multi-repo-mgmt-2026-05)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker import worktree


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(  # noqa: S603
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo(path: Path, name: str = "main") -> Path:
    """Init a real git repo at path with one commit."""
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", name], cwd=path)
    _git(["config", "user.email", "test@example.com"], cwd=path)
    _git(["config", "user.name", "Test"], cwd=path)
    (path / "README.md").write_text(f"# {path.name}\n")
    # Pre-track .gitignore — see test_worktree.py fixture rationale (avoids
    # spurious stash on "clean" base from auto-created untracked .gitignore).
    (path / ".gitignore").write_text(
        ".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n"
    )
    _git(["add", "."], cwd=path)
    _git(["commit", "-m", "init"], cwd=path)
    return path


@pytest.fixture
def primary(tmp_path: Path) -> Path:
    return _make_repo(tmp_path / "repo-a")


@pytest.fixture
def sibling(tmp_path: Path) -> Path:
    return _make_repo(tmp_path / "repo-b")


# ──────────────────────────────────────────────────────────────────────────────
# create() — return type and multi-repo behaviour
# ──────────────────────────────────────────────────────────────────────────────


def test_create_single_repo_returns_list_of_one(primary: Path) -> None:
    """Backward-compat: no sibling_dirs → list of length 1."""
    result = worktree.create("execute", primary)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].is_dir()
    assert result[0].name.startswith("execute-")


def test_create_multi_repo_returns_list_of_two(primary: Path, sibling: Path) -> None:
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    assert len(result) == 2
    primary_wt, sibling_wt = result
    assert primary_wt.is_dir()
    assert sibling_wt.is_dir()


def test_create_primary_worktree_inside_primary_repo(primary: Path, sibling: Path) -> None:
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    assert result[0].is_relative_to(primary)


def test_create_sibling_worktree_inside_sibling_repo(primary: Path, sibling: Path) -> None:
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    assert result[1].is_relative_to(sibling)


def test_create_sibling_branch_name_includes_slug(primary: Path, sibling: Path) -> None:
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    sibling_wt = result[1]
    # slug = sibling.name = "repo-b"
    assert "repo-b" in sibling_wt.name


def test_create_primary_branch_name_no_slug(primary: Path, sibling: Path) -> None:
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    primary_wt = result[0]
    # Primary branch name must NOT contain the sibling slug
    assert "repo-b" not in primary_wt.name


# ──────────────────────────────────────────────────────────────────────────────
# .hm-loop-{wt-name} marker — per-session, multi-path format (ADR-006)
# ──────────────────────────────────────────────────────────────────────────────


def test_loop_marker_contains_both_paths(primary: Path, sibling: Path) -> None:
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    # Per-session marker: .hm-loop-{primary-wt-basename}
    marker = primary / ".claude" / f".hm-loop-{result[0].name}"
    assert marker.is_file()
    content = marker.read_text(encoding="utf-8")
    lines = [ln for ln in content.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert str(result[0]) in lines
    assert str(result[1]) in lines


def test_loop_marker_single_repo_contains_one_path(primary: Path) -> None:
    result = worktree.create("execute", primary)
    marker = primary / ".claude" / f".hm-loop-{result[0].name}"
    content = marker.read_text(encoding="utf-8")
    lines = [ln for ln in content.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert str(result[0]) in lines


def test_clear_loop_marker_removes_file(primary: Path, sibling: Path) -> None:
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    marker = primary / ".claude" / f".hm-loop-{result[0].name}"
    assert marker.is_file()
    worktree._clear_loop_marker(primary, result[0].name)
    assert not marker.is_file()


# ──────────────────────────────────────────────────────────────────────────────
# _read_active_worktrees — backward-compat single-path + multi-path
# ──────────────────────────────────────────────────────────────────────────────


def test_read_active_worktrees_multi_path(primary: Path, sibling: Path) -> None:
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    paths = worktree._read_active_worktrees(primary)
    assert len(paths) == 2
    assert result[0] in paths
    assert result[1] in paths


def test_read_active_worktrees_parallel_sessions_both_visible(primary: Path, sibling: Path) -> None:
    """ADR-006: two sessions' per-session marker files → _read_active_worktrees
    returns paths from BOTH files (gate allows writes in either session)."""
    result_a = worktree.create("execute", primary)
    result_b = worktree.create("execute", primary, sibling_dirs=[sibling])
    paths = worktree._read_active_worktrees(primary)
    # Session A: 1 path; Session B: 2 paths → total 3
    assert result_a[0] in paths
    assert result_b[0] in paths
    assert result_b[1] in paths


def test_read_active_worktrees_no_marker_returns_empty(primary: Path) -> None:
    paths = worktree._read_active_worktrees(primary)
    assert paths == []


# ──────────────────────────────────────────────────────────────────────────────
# Stale execute.md sentinel detection
# ──────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────
# _cli_finalize — multi-repo fail-fast + marker retention (Phase 4)
# ──────────────────────────────────────────────────────────────────────────────


def test_finalize_all_success(primary: Path, sibling: Path) -> None:
    """All WTs finalize stage-only successfully → marker cleared, rc 0."""
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    primary_wt, sibling_wt = result

    rc = worktree._cli_finalize([str(primary_wt), "stage-only"])
    assert rc == 0

    marker = primary / ".claude" / f".hm-loop-{primary_wt.name}"
    assert not marker.is_file(), "marker must be cleared on full success"
    assert not primary_wt.is_dir(), "primary WT cleaned up"
    assert not sibling_wt.is_dir(), "sibling WT cleaned up"


def test_finalize_primary_ok_sibling_fail(
    primary: Path,
    sibling: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Primary merge succeeds; sibling merge fails → rc 1, marker kept, status to stderr."""
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    primary_wt, sibling_wt = result

    original_merge = worktree.merge

    def fail_on_sibling(wt: Path, **kwargs: object) -> None:
        if wt.is_relative_to(sibling):
            raise RuntimeError("simulated sibling merge conflict")
        original_merge(wt, **kwargs)

    monkeypatch.setattr(worktree, "merge", fail_on_sibling)

    rc = worktree._cli_finalize([str(primary_wt), "stage-only"])
    assert rc == 1

    marker = primary / ".claude" / f".hm-loop-{primary_wt.name}"
    assert marker.is_file(), "marker must be kept on partial failure (ADR-003)"

    err = capsys.readouterr().err
    assert "succeeded" in err
    assert "failed" in err


def test_finalize_rerun_after_partial(
    primary: Path,
    sibling: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-run after partial: primary WT already cleaned → skipped; sibling retried."""
    result = worktree.create("execute", primary, sibling_dirs=[sibling])
    primary_wt, sibling_wt = result

    original_merge = worktree.merge
    calls: list[Path] = []

    def fail_second_call(wt: Path, **kwargs: object) -> None:
        calls.append(wt)
        if len(calls) == 2:
            raise RuntimeError("simulated sibling fail")
        original_merge(wt, **kwargs)

    monkeypatch.setattr(worktree, "merge", fail_second_call)

    rc1 = worktree._cli_finalize([str(primary_wt), "stage-only"])
    assert rc1 == 1
    assert not primary_wt.is_dir(), "primary WT cleaned after its merge+cleanup succeeded"
    marker = primary / ".claude" / f".hm-loop-{primary_wt.name}"
    assert marker.is_file()

    monkeypatch.setattr(worktree, "merge", original_merge)
    rc2 = worktree._cli_finalize([str(primary_wt), "stage-only"])
    assert rc2 == 0
    assert not marker.is_file(), "marker cleared after full success on re-run"


def test_cli_create_stale_sentinel_emits_warning(
    primary: Path, sibling: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When sibling_repos configured but execute.md lacks sentinel → stderr warning."""
    import yaml

    # Write a harness.yaml with sibling_repos
    claude_dir = primary / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    harness_yaml = claude_dir / "harness.yaml"
    harness_data = {
        "preset": "Side",
        "locale": "en",
        "targets": ["claude-code"],
        "sibling_repos": [f"../{sibling.name}"],
        "worktree": {"scope": ["execute"]},
    }
    harness_yaml.write_text(yaml.dump(harness_data), encoding="utf-8")

    # Write execute.md WITHOUT sentinel
    cmd_dir = claude_dir / "commands" / "hm"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "execute.md").write_text("old execute.md without sentinel\n")

    # Call _cli_create directly
    worktree._cli_create(["execute", str(primary)])
    captured = capsys.readouterr()
    assert "stale" in captured.err.lower() or "update" in captured.err.lower()


def test_cli_create_with_sentinel_emits_both_paths(
    primary: Path, sibling: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When sentinel present → both paths emitted to stdout."""
    import yaml

    claude_dir = primary / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    harness_yaml = claude_dir / "harness.yaml"
    harness_data = {
        "preset": "Side",
        "locale": "en",
        "targets": ["claude-code"],
        "sibling_repos": [f"../{sibling.name}"],
        "worktree": {"scope": ["execute"]},
    }
    harness_yaml.write_text(yaml.dump(harness_data), encoding="utf-8")

    # Write execute.md WITH sentinel
    cmd_dir = claude_dir / "commands" / "hm"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "execute.md").write_text("# SIBLING_WORKTREE_PATHS\nsome instructions\n")

    import io
    import sys

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        worktree._cli_create(["execute", str(primary)])
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    lines = [ln for ln in output.splitlines() if ln.strip()]
    assert len(lines) == 2
    # First line = primary repo path
    assert str(primary) in lines[0]
    # Second line = sibling repo path
    assert str(sibling) in lines[1]


def test_cli_create_with_provenance_frontmatter_resolves_siblings(
    primary: Path, sibling: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`_load_sibling_dirs` resolves sibling paths from a real (provenance-prefixed) harness.yaml.

    Regression guard for the io_utils.load_harness_yaml migration
    (docs/followups/io-utils-migration.md). Production harness.yaml always
    carries the renderer's provenance frontmatter block as the FIRST YAML
    document; `_load_sibling_dirs` must still find `sibling_repos` in the
    user-body doc. Pre-migration coverage used `yaml.dump` (bare single-doc)
    so the multi-document path was uncovered.
    """
    import io
    import sys

    import yaml

    claude_dir = primary / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    harness_yaml = claude_dir / "harness.yaml"
    provenance = (
        "---\n"
        "generated_by: harness-maker\n"
        "harness_maker_version: 0.13.0\n"
        "generated_at: '2026-01-01T00:00:00+00:00'\n"
        "source_template: harness-yaml/Side.yaml.j2\n"
        "provenance: official\n"
        "content_hash: " + "0" * 64 + "\n"
        "---\n"
    )
    body = yaml.dump(
        {
            "preset": "Side",
            "locale": "en",
            "targets": ["claude-code"],
            "sibling_repos": [f"../{sibling.name}"],
            "worktree": {"scope": ["execute"]},
        }
    )
    harness_yaml.write_text(provenance + body, encoding="utf-8")

    cmd_dir = claude_dir / "commands" / "hm"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "execute.md").write_text("# SIBLING_WORKTREE_PATHS\nbody\n")

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        worktree._cli_create(["execute", str(primary)])
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    lines = [ln for ln in output.splitlines() if ln.strip()]
    # Provenance frontmatter must NOT block sibling resolution — both paths emit.
    assert len(lines) == 2
    assert str(primary) in lines[0]
    assert str(sibling) in lines[1]


# ──────────────────────────────────────────────────────────────────────────────
# _OWNED_PREFIXES filter (PLAN-untested-trio-fix ADR-002 + ADR-004)
# ──────────────────────────────────────────────────────────────────────────────


def test_list_worktrees_only_includes_owned_prefixes(primary: Path) -> None:
    """_list_worktrees must filter out non-owned-prefix worktrees (ADR-002 + ADR-004).

    Creates owned (execute-) and unowned (cursor-) worktrees. Only the owned
    one appears in _list_worktrees output. Mirrors the Cursor-IDE-cross-tool
    scenario where another tool's worktree must not be visible to cleanup_all.
    """
    owned = worktree.create("execute", primary)
    unowned = worktree.create("cursor-bar", primary)

    listed = worktree._list_worktrees(primary)
    listed_names = [p.name for p in listed]

    assert owned[0].name in listed_names, (
        f"owned worktree missing from _list_worktrees: {listed_names}"
    )
    assert unowned[0].name not in listed_names, (
        f"unowned worktree leaked into _list_worktrees: {listed_names}"
    )


def test_cleanup_all_does_not_touch_unowned_worktrees(primary: Path) -> None:
    """cleanup_all must leave non-owned-prefix worktrees registered (ADR-002).

    Cursor (or any other tool) creating a `.worktrees/<other-prefix>/` worktree
    must survive `cleanup_all(force=True)`. This is the load-bearing cross-tool
    safety claim from CLAUDE.md §"Worktree 공유".
    """
    owned = worktree.create("execute", primary)
    unowned = worktree.create("cursor-bar", primary)

    removed = worktree.cleanup_all(primary, force=True)

    assert removed == 1, f"expected 1 owned removal, got {removed}"
    assert not owned[0].exists(), f"owned worktree survived cleanup: {owned[0]}"
    assert unowned[0].exists(), f"unowned worktree removed by cleanup: {unowned[0]}"

    # Verify unowned is still registered with git (cleanup must not have run
    # `git worktree remove` against it).
    out = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(primary),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert str(unowned[0]) in out, f"unowned worktree unregistered from git: {out}"
