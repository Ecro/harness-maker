from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

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
    # ADR-001 `.git`-filter: only a dir that IS a worktree (has a `.git` entry)
    # is reapable. A genuine orphan from a crashed session has its `.git` file.
    (dangling_wt / ".git").write_text("gitdir: /gone\n")

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


# ── ADR-001: pre-create reservation + `.git` filter (prune-create race) ───────


def _owned_dir_with_git(repo: Path, name: str) -> Path:
    """A `.worktrees/<owned>` dir that LOOKS like a real worktree (has `.git`),
    unregistered + unmarked → the genuine-orphan shape that IS reapable."""
    wt = repo / ".worktrees" / name
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: /gone\n")
    return wt


def test_fresh_reservation_protects_in_flight_dir(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    wt = _owned_dir_with_git(repo, "execute-inflight012-20260621T0000Z")
    # a peer's create() wrote a FRESH reservation before its `git worktree add`
    worktree.atomic_write(worktree._reservation_path(repo, wt.name), "peer-uuid\n")
    report = worktree.prune_stale(repo)
    assert wt not in report.removed_worktrees
    assert wt.exists()  # in-flight peer dir survives


def test_aged_reservation_does_not_protect_and_is_removed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    wt = _owned_dir_with_git(repo, "execute-stalecreate-20260621T0000Z")
    reservation = worktree._reservation_path(repo, wt.name)
    worktree.atomic_write(reservation, "dead-uuid\n")
    old = time.time() - worktree._PRUNE_GRACE_SECONDS - 60
    os.utime(reservation, (old, old))
    report = worktree.prune_stale(repo)
    assert wt in report.removed_worktrees
    assert not wt.exists()
    assert not reservation.exists()  # stale reservation reaped too


def test_dir_without_git_is_not_reaped(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    wt = repo / ".worktrees" / "execute-nogitdir12-20260621T0000Z"
    wt.mkdir(parents=True)  # owned prefix, unregistered, unmarked, but NO `.git`
    report = worktree.prune_stale(repo)
    assert wt not in report.removed_worktrees
    assert wt.exists()  # non-worktree dir preserved (`.git` filter)


def test_orphan_with_git_no_reservation_is_reaped(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    wt = _owned_dir_with_git(repo, "execute-realorphan-20260621T0000Z")
    report = worktree.prune_stale(repo)
    assert wt in report.removed_worktrees
    assert not wt.exists()  # genuine orphan still reaped


def test_create_removes_reservation_on_success(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wts = worktree.create("execute", repo)
    name = wts[0].name
    assert not worktree._reservation_path(repo, name).exists()


def test_create_removes_reservation_on_add_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    real_run = worktree._run

    def boom(args: list[str], cwd: Path, **kw: object) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "worktree", "add"]:
            raise RuntimeError("simulated git worktree add failure")
        return real_run(args, cwd=cwd, **kw)

    monkeypatch.setattr(worktree, "_run", boom)
    with pytest.raises(RuntimeError):
        worktree.create("execute", repo)
    # no reservation left behind under .claude/ even though the add failed
    claude = repo / ".claude"
    leftover = list(claude.glob(".hm-creating-*")) if claude.is_dir() else []
    assert leftover == []


# ── ADR-002: `git worktree prune --expire` (de-registration vector) ───────────


def test_git_expire_arg_accepted_by_installed_git(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    arg = worktree._git_expire_arg(worktree._PRUNE_GRACE_SECONDS)
    cp = subprocess.run(  # noqa: S603
        ["git", "worktree", "prune", f"--expire={arg}", "--dry-run"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0, cp.stderr


def test_expire_keeps_recent_prunable_admin_entry_but_reaps_aged(tmp_path: Path) -> None:
    import shutil

    repo = _repo(tmp_path)
    name = "execute-recentadm12-20260621T0000Z"
    wt = repo / ".worktrees" / name
    _git(["worktree", "add", "-b", name, str(wt)], repo)
    shutil.rmtree(wt)  # leaf gone → admin entry is now prunable by a BARE prune
    admin = repo / ".git" / "worktrees" / name
    assert admin.is_dir()

    # create-time prune with --expire keeps the RECENT admin entry (a bare prune
    # would de-register it — the de-registration vector ADR-002 closes).
    worktree.prune_stale(repo)
    assert admin.is_dir()  # recent → survives

    # age the admin entry past grace → next prune de-registers it
    old = time.time() - worktree._PRUNE_GRACE_SECONDS - 120
    for f in admin.rglob("*"):
        os.utime(f, (old, old))
    os.utime(admin, (old, old))
    worktree.prune_stale(repo)
    assert not admin.is_dir()  # aged → de-registered


# ── ADR-003: marker-strand fix — preserve a marker with a pending stash ───────


def test_orphan_marker_with_pending_stash_is_preserved(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir()
    wt_name = "execute-strand12345-20260621T0000Z"
    missing_wt = repo / ".worktrees" / wt_name  # dir already cleaned up by finalize
    marker = claude / f".hm-loop-{wt_name}"
    marker.write_text(f"{missing_wt}\n")
    # a real pending stash ref whose session_marker points at THIS marker
    (repo / "tracked.txt").write_text("deferred dirty\n")
    _git(["stash", "push", "-u", "-m", "deferred"], repo)
    ref_sha = _git(["rev-parse", "stash@{0}"], repo)
    worktree._write_stash_ref_file(repo, wt_name, ref_sha, marker)

    assert worktree._is_orphan_marker(marker) is False
    report = worktree.prune_stale(repo)
    assert marker not in report.removed_markers
    assert marker.exists()  # survives → post-commit-pop can still find it


def test_orphan_marker_without_pending_stash_still_pruned(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir()
    wt_name = "execute-nopending12-20260621T0000Z"
    missing_wt = repo / ".worktrees" / wt_name
    marker = claude / f".hm-loop-{wt_name}"
    marker.write_text(f"{missing_wt}\n")

    assert worktree._is_orphan_marker(marker) is True
    report = worktree.prune_stale(repo)
    assert marker in report.removed_markers  # unchanged: no stash → still pruned


def test_primary_marker_preserved_by_sibling_only_pending_stash(tmp_path: Path) -> None:
    # multi-repo (validator W2): the ref FILENAME is sibling-suffixed, but its
    # `session_marker` content field points at the PRIMARY marker. A filename-stem
    # join would miss it; the content-field join preserves the primary marker.
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir()
    primary = "execute-multirepo1-20260621T0000Z"
    missing_wt = repo / ".worktrees" / primary
    marker = claude / f".hm-loop-{primary}"
    marker.write_text(f"{missing_wt}\n")
    # a real pending stash written with a SIBLING-suffixed ref filename, whose
    # session_marker content points at the PRIMARY marker (the multi-repo shape).
    (repo / "tracked.txt").write_text("sibling deferred\n")
    _git(["stash", "push", "-u", "-m", "sib"], repo)
    ref_sha = _git(["rev-parse", "stash@{0}"], repo)
    ref = worktree._write_stash_ref_file(repo, f"{primary}-mysibling", ref_sha, marker)
    assert "mysibling" in ref.name  # filename stem differs from the primary marker
    assert worktree._is_orphan_marker(marker) is False  # primary preserved (content join)


# ── REVIEW fixes: dead-stash marker not immortalized + aged reservation reaped ──


def test_orphan_marker_with_dead_stash_is_still_pruned(tmp_path: Path) -> None:
    """REVIEW Codex P2: a marker whose only matching stash ref is DEAD (content
    already in HEAD) must NOT be immortalized — else marker+ref deadlock forever."""
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir(exist_ok=True)
    # a stash whose content is already committed to HEAD → drainable/dead
    (repo / "tracked.txt").write_text("changed\n")
    _git(["stash", "push", "-u", "-m", "dead"], repo)
    ref_sha = _git(["rev-parse", "stash@{0}"], repo)
    (repo / "tracked.txt").write_text("changed\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "content now in head"], repo)

    claude.mkdir(exist_ok=True)  # `git stash -u` removed the empty .claude/ dir
    wt_name = "execute-deadstash12-20260621T0000Z"
    missing_wt = repo / ".worktrees" / wt_name
    marker = claude / f".hm-loop-{wt_name}"
    marker.write_text(f"{missing_wt}\n")
    worktree._write_stash_ref_file(repo, wt_name, ref_sha, marker)

    # the ref is dead (content in HEAD) → it does NOT preserve the marker
    assert worktree._is_orphan_marker(marker) is True
    report = worktree.prune_stale(repo)
    assert marker in report.removed_markers


def test_prune_stale_reaps_aged_leaked_reservation(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir()
    reservation = worktree._reservation_path(repo, "execute-leaked12345-20260621T0000Z")
    worktree.atomic_write(reservation, "killed\n")
    old = time.time() - worktree._PRUNE_GRACE_SECONDS - 60
    os.utime(reservation, (old, old))

    worktree.prune_stale(repo)
    assert not reservation.exists()  # aged leaked reservation reaped


def test_prune_stale_keeps_fresh_reservation(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir()
    reservation = worktree._reservation_path(repo, "execute-livecreate1-20260621T0000Z")
    worktree.atomic_write(reservation, "creating\n")  # fresh

    worktree.prune_stale(repo)
    assert reservation.exists()  # a live create's reservation is never reaped
