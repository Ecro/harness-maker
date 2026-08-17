"""Phase 4 (PLAN-worktree-prune-create-race) — concurrent reservation race.

Deterministic proofs that a peer session's in-flight worktree survives a
concurrent create-time `prune_stale`. The per-predicate unit proofs live in
`test_worktree_prune.py` (reservation-fresh-preserved, `.git`-filter, marker
strand); these drive REAL concurrency to exercise the reservation under threads.
"""

from __future__ import annotations

import contextlib
import subprocess
import threading
import time
from pathlib import Path

from harness_maker import worktree
from harness_maker.io_utils import atomic_write


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
    (repo / ".gitignore").write_text(".worktrees/\n.claude/.hm-loop-*\n")
    (repo / "f.txt").write_text("base\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def test_reserved_dir_survives_concurrent_prune_hammer(tmp_path: Path) -> None:
    """An in-flight dir (exists with `.git`, fresh reservation held) is never
    rmtree'd by N concurrent prune_stale calls."""
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    name = "execute-inflightX12-20260621T0000Z"
    wt = repo / ".worktrees" / name
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: /gone\n")
    atomic_write(worktree._reservation_path(repo, name), "peer\n")

    stop = threading.Event()
    removed: list[Path] = []

    def hammer() -> None:
        while not stop.is_set():
            report = worktree.prune_stale(repo)
            removed.extend(report.removed_worktrees)

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for t in threads:
        t.start()
    time.sleep(0.3)
    stop.set()
    for t in threads:
        t.join(timeout=5)

    assert wt.exists(), "reserved in-flight dir was rmtree'd by a concurrent prune"
    assert wt.resolve() not in removed


def test_concurrent_create_is_never_reaped_mid_flight(tmp_path: Path) -> None:
    """A real `create()` running concurrently with a prune hammer always returns a
    live worktree — the reservation covers the add→marker window."""
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()

    stop = threading.Event()
    result: dict[str, Path] = {}
    errors: list[Exception] = []

    def do_create() -> None:
        try:
            wts = worktree.create("execute", repo)
            result["wt"] = wts[0]
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def hammer() -> None:
        while not stop.is_set():
            with contextlib.suppress(Exception):
                worktree.prune_stale(repo)

    h = threading.Thread(target=hammer)
    h.start()
    c = threading.Thread(target=do_create)
    c.start()
    c.join(timeout=20)
    stop.set()
    h.join(timeout=5)

    assert not errors, f"create() failed under concurrent prune: {errors}"
    assert "wt" in result
    assert result["wt"].exists()
    # the reservation was cleaned up after create completed
    assert not worktree._reservation_path(repo, result["wt"].name).exists()
