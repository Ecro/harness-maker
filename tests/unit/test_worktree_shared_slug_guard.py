"""Fix 1 (PLAN-multisession-10-fleet-hardening ADR-001) — same-slug foreign-live
hard-fail with `--allow-shared-slug` escape hatch.

Two independent sessions choosing the same feature slug must NOT silently share
`.worktrees/<slug>/` + `hm/<slug>`. A foreign LIVE session holding the branch makes
`claim_task_branch` raise `SharedSlugError`; own-uuid re-entry still attaches; the
escape hatch permits intentional pairing. The claim's foreign-live check + branch
claim are one atomic `_registry_mutate` critical section (no check-then-act TOCTOU).
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from harness_maker import worktree
from harness_maker.worktree import (
    SessionRow,
    SharedSlugError,
    _read_sessions,
    _write_sessions,
    claim_task_branch,
    task_branch,
)


def _seed(base: Path, *, branch: str, uuid: str, pid: int, wt: Path) -> None:
    wt.mkdir(parents=True, exist_ok=True)
    _write_sessions(
        base,
        [
            SessionRow(
                task="x",
                branch=branch,
                worktree=str(wt),
                session_uuid=uuid,
                pid=pid,
                created_at="2026-06-21T00:00:00Z",
            )
        ],
    )


# ── base-class contract (load-bearing — must NOT be swallowed by _registry_mutate) ──


def test_shared_slug_error_is_not_runtimeerror() -> None:
    """`_registry_mutate` catches (TimeoutError, RuntimeError, OSError); a
    RuntimeError subclass would be swallowed onto the unfenced fallback."""
    assert issubclass(SharedSlugError, Exception)
    assert not issubclass(SharedSlugError, (RuntimeError, OSError))


# ── claim guard ──────────────────────────────────────────────────────────────


def test_foreign_live_same_branch_raises(tmp_path: Path) -> None:
    branch = task_branch("featureA")
    _seed(tmp_path, branch=branch, uuid="foreign", pid=os.getpid(), wt=tmp_path / "wt")
    with pytest.raises(SharedSlugError):
        claim_task_branch(
            tmp_path,
            task="featureA",
            branch=branch,
            wt=str(tmp_path / "wt"),
            session_uuid="mine",
            pid=os.getpid(),
            allow_shared=False,
        )


def test_own_uuid_reentry_attaches(tmp_path: Path) -> None:
    branch = task_branch("featureA")
    _seed(tmp_path, branch=branch, uuid="mine", pid=os.getpid(), wt=tmp_path / "wt")
    # Same uuid re-claim must NOT raise (crash-recovery / idempotent re-run).
    claim_task_branch(
        tmp_path,
        task="featureA",
        branch=branch,
        wt=str(tmp_path / "wt"),
        session_uuid="mine",
        pid=os.getpid(),
        allow_shared=False,
    )
    rows = _read_sessions(tmp_path)
    assert [r.session_uuid for r in rows] == ["mine"]


def test_allow_shared_proceeds(tmp_path: Path) -> None:
    branch = task_branch("featureA")
    _seed(tmp_path, branch=branch, uuid="foreign", pid=os.getpid(), wt=tmp_path / "wt")
    claim_task_branch(
        tmp_path,
        task="featureA",
        branch=branch,
        wt=str(tmp_path / "wt"),
        session_uuid="mine",
        pid=os.getpid(),
        allow_shared=True,
    )
    # Both rows now coexist (intentional sharing).
    uuids = {r.session_uuid for r in _read_sessions(tmp_path)}
    assert uuids == {"foreign", "mine"}


def test_dead_foreign_row_does_not_block(tmp_path: Path) -> None:
    """A foreign row whose pid is dead is not 'live' → claim proceeds."""
    branch = task_branch("featureA")
    dead = 2**31 - 1  # implausible pid → _pid_alive False
    _seed(tmp_path, branch=branch, uuid="foreign", pid=dead, wt=tmp_path / "wt")
    claim_task_branch(
        tmp_path,
        task="featureA",
        branch=branch,
        wt=str(tmp_path / "wt"),
        session_uuid="mine",
        pid=os.getpid(),
        allow_shared=False,
    )
    assert "mine" in {r.session_uuid for r in _read_sessions(tmp_path)}


def test_missing_worktree_dir_foreign_row_does_not_block(tmp_path: Path) -> None:
    """A foreign live-pid row whose worktree dir is absent matches reclaim's
    'dead' definition → does not block (the truly-simultaneous pre-create window
    is covered by git worktree-add atomicity, not this check)."""
    branch = task_branch("featureA")
    _write_sessions(
        tmp_path,
        [
            SessionRow(
                task="x",
                branch=branch,
                worktree=str(tmp_path / "gone"),  # never created
                session_uuid="foreign",
                pid=os.getpid(),
                created_at="2026-06-21T00:00:00Z",
            )
        ],
    )
    claim_task_branch(
        tmp_path,
        task="featureA",
        branch=branch,
        wt=str(tmp_path / "wt"),
        session_uuid="mine",
        pid=os.getpid(),
        allow_shared=False,
    )
    assert "mine" in {r.session_uuid for r in _read_sessions(tmp_path)}


# ── atomicity (check + claim in one critical section) ────────────────────────


def test_concurrent_claims_exactly_one_wins(tmp_path: Path) -> None:
    """Two threads claim the same branch with distinct uuids; the foreign-live
    predicate fires (shared wt dir exists, same live pid) so exactly one wins and
    the other raises — proving the check+insert is atomic, not check-then-act."""
    branch = task_branch("featureA")
    wt = tmp_path / "wt"
    wt.mkdir()
    results: dict[str, str] = {}
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def worker(uid: str) -> None:
        barrier.wait()
        try:
            claim_task_branch(
                tmp_path,
                task="featureA",
                branch=branch,
                wt=str(wt),
                session_uuid=uid,
                pid=os.getpid(),
                allow_shared=False,
            )
            with lock:
                results[uid] = "won"
        except SharedSlugError:
            with lock:
                results[uid] = "raised"

    t1 = threading.Thread(target=worker, args=("u1",))
    t2 = threading.Thread(target=worker, args=("u2",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert sorted(results.values()) == ["raised", "won"], results


# ── fail-closed on a wedged registry lock (REVIEW k-of-3 P1) ─────────────────


def test_wedged_lock_claim_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the registry lock is unavailable, a NON-shared claim must fail closed
    (SharedSlugError) rather than silently fall back to an unfenced share."""
    import contextlib

    @contextlib.contextmanager
    def _wedged(*_a: object, **_k: object):  # type: ignore[no-untyped-def]
        raise TimeoutError("registry lock wedged")
        yield  # pragma: no cover

    monkeypatch.setattr(worktree, "_acquire_merge_fence", _wedged)
    with pytest.raises(SharedSlugError):
        claim_task_branch(
            tmp_path,
            task="featureA",
            branch=task_branch("featureA"),
            wt=str(tmp_path / "wt"),
            session_uuid="mine",
            pid=os.getpid(),
            allow_shared=False,
        )


def test_wedged_lock_allow_shared_proceeds_unfenced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With allow_shared the share is intentional, so a wedged lock degrades to the
    best-effort unfenced path (no fail-closed)."""
    import contextlib

    @contextlib.contextmanager
    def _wedged(*_a: object, **_k: object):  # type: ignore[no-untyped-def]
        raise TimeoutError("registry lock wedged")
        yield  # pragma: no cover

    monkeypatch.setattr(worktree, "_acquire_merge_fence", _wedged)
    claim_task_branch(
        tmp_path,
        task="featureA",
        branch=task_branch("featureA"),
        wt=str(tmp_path / "wt"),
        session_uuid="mine",
        pid=os.getpid(),
        allow_shared=True,
    )
    assert "mine" in {r.session_uuid for r in _read_sessions(tmp_path)}
