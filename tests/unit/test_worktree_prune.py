from __future__ import annotations

import subprocess
from pathlib import Path

from harness_maker import worktree


def _git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(  # noqa: S603
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return cp.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n.claude/.hm-loop-*\n")
    (repo / "tracked.txt").write_text("base\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def test_prune_stale_removes_orphan_marker_and_dangling_owned_dir(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir()
    missing_wt = repo / ".worktrees" / "execute-deadbeef1234-20260525T0000Z"
    live_wt = repo / ".worktrees" / "execute-livefeed123-20260525T0000Z"
    dangling_wt = repo / ".worktrees" / "execute-orphaned12-20260525T0000Z"
    non_owned_wt = repo / ".worktrees" / "cursor-foo"
    live_wt.mkdir(parents=True)
    dangling_wt.mkdir(parents=True)
    non_owned_wt.mkdir(parents=True)

    orphan_marker = claude / f".hm-loop-{missing_wt.name}"
    live_marker = claude / f".hm-loop-{live_wt.name}"
    orphan_marker.write_text(f"{missing_wt}\n")
    live_marker.write_text(f"{live_wt}\n")

    report = worktree.prune_stale(repo)

    assert orphan_marker in report.removed_markers
    assert not orphan_marker.exists()
    assert live_marker.exists()
    assert dangling_wt in report.removed_worktrees
    assert not dangling_wt.exists()
    assert non_owned_wt.exists()


def test_stale_finalize_ref_deleted_only_when_tracked_and_untracked_in_head(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir(exist_ok=True)

    (repo / "tracked.txt").write_text("changed\n")
    (repo / "new.txt").write_text("new\n")
    _git(["stash", "push", "-u", "-m", "hm-test"], repo)
    ref_sha = _git(["rev-parse", "stash@{0}"], repo)

    (repo / "tracked.txt").write_text("changed\n")
    (repo / "new.txt").write_text("new\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "same content in head"], repo)

    wt_name = "execute-deadbeef1234-20260525T0000Z"
    marker = repo / ".claude" / f".hm-loop-{wt_name}"
    ref_file = worktree._write_stash_ref_file(repo, wt_name, ref_sha, marker)

    report = worktree.prune_stale(repo)

    assert ref_file in report.removed_stash_refs
    assert not ref_file.exists()


def test_stale_finalize_ref_preserved_when_untracked_blob_absent_from_head(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir(exist_ok=True)

    (repo / "tracked.txt").write_text("changed\n")
    (repo / "new.txt").write_text("new\n")
    _git(["stash", "push", "-u", "-m", "hm-test"], repo)
    ref_sha = _git(["rev-parse", "stash@{0}"], repo)

    (repo / "tracked.txt").write_text("changed\n")
    _git(["add", "tracked.txt"], repo)
    _git(["commit", "-m", "tracked content only"], repo)

    wt_name = "execute-deadbeef1234-20260525T0000Z"
    marker = repo / ".claude" / f".hm-loop-{wt_name}"
    ref_file = worktree._write_stash_ref_file(repo, wt_name, ref_sha, marker)

    report = worktree.prune_stale(repo)

    assert ref_file.exists()
    assert report.preserved_stash_refs
    assert ref_file == report.preserved_stash_refs[0][0]


def test_queue_guard_ignores_stale_ref_with_absent_marker(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir(exist_ok=True)
    for idx in range(2):
        ref_file = claude / f".hm-finalize-stash-execute-deadbeef123{idx}-20260525T0000Z"
        ref_file.write_text(
            "ref_sha: " + ("a" * 40) + "\n"
            f"base: {repo}\n"
            f"session_marker: {claude}/.hm-loop-execute-deadbeef123{idx}-20260525T0000Z\n"
            "sibling_bases: \n"
            f"session_uuid: deadbeef123{idx}\n"
            "created_at: 2026-05-25T00:00:00+00:00\n"
        )

    assert worktree._count_pending_stashes(claude) == 0
