"""Fix 3 (PLAN-multisession-10-fleet-hardening ADR-003) — pid+nonce O_EXCL lock
with liveness-gated reap-at-acquire.

The O_EXCL fallback lock (`_excl_lock`) gains a `nonce\\npid\\ntimestamp` body so
a SIGKILL'd holder's stale lock self-heals on the next acquire WITHOUT ever
reaping a still-live holder by age (the fence acquire-timeout bounds waiting,
not hold time). Reaping is liveness-gated; reap + release are nonce-identity
checked so a successor's lock is never unlinked.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from harness_maker.worktree import (
    _EXCL_STALE_AGE,
    _excl_lock,
    _excl_release,
    _parse_excl_body,
    _reap_if_stale,
)


def _dead_pid() -> int:
    """A genuinely-dead pid: spawn a trivial child, reap it, return its pid."""
    proc = subprocess.Popen(["true"])  # noqa: S603,S607
    proc.wait()
    return proc.pid


def _write_body(path: Path, *, nonce: str, pid: int, ts: float) -> None:
    path.write_text(f"{nonce}\n{pid}\n{ts}\n", encoding="utf-8")


def _age(path: Path, seconds: float) -> None:
    """Backdate a file's mtime by `seconds`."""
    old = time.time() - seconds
    os.utime(path, (old, old))


# ── body parsing ─────────────────────────────────────────────────────────────


def test_parse_excl_body_roundtrip() -> None:
    nonce, pid, ts = _parse_excl_body("abc123\n4242\n1000.5\n")
    assert nonce == "abc123"
    assert pid == 4242
    assert ts == 1000.5


def test_parse_excl_body_empty_is_all_none() -> None:
    assert _parse_excl_body("") == (None, None, None)


def test_parse_excl_body_garbage_pid_is_none() -> None:
    nonce, pid, _ts = _parse_excl_body("nonce\nnotanint\n123.0\n")
    assert nonce == "nonce"
    assert pid is None


# ── reap gating ──────────────────────────────────────────────────────────────


def test_reap_dead_pid_holder(tmp_path: Path) -> None:
    """A lock whose holder pid is dead → reaped (the SIGKILL case)."""
    lock = tmp_path / "index.lock-hm-registry-excl"
    _write_body(lock, nonce="n1", pid=_dead_pid(), ts=time.time())
    assert _reap_if_stale(lock) is True
    assert not lock.exists()


def test_live_pid_holder_never_reaped_even_when_aged(tmp_path: Path) -> None:
    """A LIVE holder (our own pid) is NEVER reaped by age — mutual exclusion
    must hold even for a legitimately slow/hung land (Codex P0)."""
    lock = tmp_path / "index.lock-hm-registry-excl"
    _write_body(lock, nonce="n1", pid=os.getpid(), ts=time.time())
    _age(lock, _EXCL_STALE_AGE + 600)  # far past the age threshold
    assert _reap_if_stale(lock) is False
    assert lock.exists()


def test_unparseable_body_aged_is_reaped(tmp_path: Path) -> None:
    """An empty/legacy body (e.g. SIGKILL in the create→write window) is reaped
    only once mtime exceeds the age threshold."""
    lock = tmp_path / "index.lock-hm-registry-excl"
    lock.write_text("", encoding="utf-8")
    _age(lock, _EXCL_STALE_AGE + 5)
    assert _reap_if_stale(lock) is True
    assert not lock.exists()


def test_unparseable_body_fresh_not_reaped(tmp_path: Path) -> None:
    """A fresh empty body is NOT reaped — the create→write window must not
    manufacture an immediate reap of a just-created live lock."""
    lock = tmp_path / "index.lock-hm-registry-excl"
    lock.write_text("", encoding="utf-8")  # mtime = now
    assert _reap_if_stale(lock) is False
    assert lock.exists()


def test_reap_abandoned_when_body_changed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TOCTOU: if a successor recreates the lock (different body) between the
    staleness decision and the unlink, the reap is abandoned (Codex P1)."""
    lock = tmp_path / "index.lock-hm-registry-excl"
    dead = _dead_pid()
    _write_body(lock, nonce="old", pid=dead, ts=time.time())

    real_pid_alive = None
    from harness_maker import worktree

    real_pid_alive = worktree._pid_alive

    def racing_pid_alive(pid: int) -> bool:
        # Simulate a successor overwriting the lock right after we decide it's stale.
        _write_body(lock, nonce="successor", pid=os.getpid(), ts=time.time())
        return real_pid_alive(pid)

    monkeypatch.setattr(worktree, "_pid_alive", racing_pid_alive)
    assert _reap_if_stale(lock) is False
    assert lock.exists()  # successor's lock survived


# ── identity-checked release ─────────────────────────────────────────────────


def test_release_unlinks_own_nonce(tmp_path: Path) -> None:
    lock = tmp_path / "index.lock-hm-registry-excl"
    _write_body(lock, nonce="mine", pid=os.getpid(), ts=time.time())
    _excl_release(lock, "mine")
    assert not lock.exists()


def test_release_preserves_foreign_nonce(tmp_path: Path) -> None:
    """Release must never unlink a successor's lock (different nonce)."""
    lock = tmp_path / "index.lock-hm-registry-excl"
    _write_body(lock, nonce="successor", pid=os.getpid(), ts=time.time())
    _excl_release(lock, "mine")  # our nonce no longer occupies the file
    assert lock.exists()


# ── acquire end-to-end ───────────────────────────────────────────────────────


def test_excl_lock_returns_fd_and_nonce_and_stamps_body(tmp_path: Path) -> None:
    lock = tmp_path / "index.lock-hm-registry-excl"
    fd, nonce = _excl_lock(lock, timeout=1.0)
    try:
        assert isinstance(fd, int)
        assert nonce
        body_nonce, body_pid, _ts = _parse_excl_body(lock.read_text(encoding="utf-8"))
        assert body_nonce == nonce
        assert body_pid == os.getpid()
    finally:
        os.close(fd)
        _excl_release(lock, nonce)


def test_excl_lock_reaps_dead_holder_then_acquires(tmp_path: Path) -> None:
    """A pre-existing lock from a dead holder is reaped and the new acquire wins."""
    lock = tmp_path / "index.lock-hm-registry-excl"
    _write_body(lock, nonce="stale", pid=_dead_pid(), ts=time.time())
    fd, nonce = _excl_lock(lock, timeout=2.0)
    try:
        assert nonce != "stale"
    finally:
        os.close(fd)
        _excl_release(lock, nonce)


def test_excl_lock_times_out_on_live_holder(tmp_path: Path) -> None:
    """A live holder's lock is not reaped → acquire blocks to timeout."""
    lock = tmp_path / "index.lock-hm-registry-excl"
    _write_body(lock, nonce="live", pid=os.getpid(), ts=time.time())
    _age(lock, _EXCL_STALE_AGE + 600)
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        _excl_lock(lock, timeout=0.4)
    assert 0.2 < time.monotonic() - start < 1.5


def test_excl_lock_body_write_failure_is_acquisition_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW Codex P2: a short/failed body write must NOT hand back a lock that
    `_excl_release` cannot identify — it self-cleans and keeps polling, leaving no
    leftover lock to wedge the fence."""
    real_write = os.write

    def short_write(fd: int, data: bytes) -> int:
        real_write(fd, data[:-1])  # actually write a short body
        return len(data) - 1  # report short

    monkeypatch.setattr(os, "write", short_write)
    lock = tmp_path / "index.lock-hm-registry-excl"
    with pytest.raises(TimeoutError):
        _excl_lock(lock, timeout=0.3)
    monkeypatch.undo()
    assert not lock.exists()  # no half-written lock left to wedge the fence
