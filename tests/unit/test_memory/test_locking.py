"""Tests for cross-process file lock helper (ADR-106, 0.7.1)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.memory._locking import exclusive_lock


def test_exclusive_lock_reentrant_no_deadlock(tmp_path: Path) -> None:
    """Same thread acquiring the same lock twice must NOT deadlock —
    the inner ``with`` block yields immediately. ADR-106."""
    lock_path = tmp_path / "x.lock"
    inner_ran = False
    with exclusive_lock(lock_path), exclusive_lock(lock_path):
        inner_ran = True
    assert inner_ran is True


def test_exclusive_lock_distinct_paths_serialise_independently(tmp_path: Path) -> None:
    """Different lock paths use independent depth counters — nesting
    different locks in one thread does not collide."""
    lock_a = tmp_path / "a.lock"
    lock_b = tmp_path / "b.lock"
    with (
        exclusive_lock(lock_a),
        exclusive_lock(lock_b),
        exclusive_lock(lock_a),  # re-enter A while holding B
    ):
        pass


def test_exclusive_lock_releases_after_context(tmp_path: Path) -> None:
    """Lock must be releasable for a fresh acquire after the with block.
    Verifies depth counter resets to 0 (no leak)."""
    lock_path = tmp_path / "y.lock"
    with exclusive_lock(lock_path):
        pass
    # Second acquire should not block — flock_lock_path counter is back to 0.
    with exclusive_lock(lock_path):
        pass
