"""Tests for profile memory layer."""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

from harness_maker.memory.profile import ProfileStore


def _profile_worker(base_dir: str, worker_id: int, n: int) -> None:
    """Top-level worker for multiprocessing.Process — distinct keys per writer."""
    store = ProfileStore(Path(base_dir))
    for i in range(n):
        store.set(f"w{worker_id}-{i}", {"v": i})


def test_set_and_get(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    store.set("preferred_style", "concise")
    assert store.get("preferred_style") == "concise"


def test_get_nonexistent_returns_none(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    assert store.get("missing") is None


def test_set_overwrites_with_history(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    store.set("style", "verbose", timestamp="t1")
    store.set("style", "concise", timestamp="t2")
    assert store.get("style") == "concise"
    data = store.get_all()
    assert len(data["style"]["history"]) == 1
    assert data["style"]["history"][0]["value"] == "verbose"


def test_get_all(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    store.set("a", 1)
    store.set("b", 2)
    data = store.get_all()
    assert "a" in data
    assert "b" in data


def test_empty_store(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    assert store.get_all() == {}


def test_concurrent_set_no_lost_update(tmp_path: Path) -> None:
    """4 processes × 25 distinct keys each: profile must contain all 100 keys.

    Validates Phase 12a flock fix for the read-modify-replace lost-update race
    that previously caused profile keys from concurrent set() calls to be
    silently dropped.
    """
    n_per_worker = 25
    n_workers = 4
    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_profile_worker, args=(str(tmp_path), wid, n_per_worker))
        for wid in range(n_workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert not p.is_alive(), "worker timed out"
        assert p.exitcode == 0, f"worker exited with {p.exitcode}"
    store = ProfileStore(tmp_path)
    data = store.get_all()
    assert len(data) == n_per_worker * n_workers, (
        f"expected {n_per_worker * n_workers} keys, got {len(data)}"
    )
    expected = {f"w{wid}-{i}" for wid in range(n_workers) for i in range(n_per_worker)}
    assert set(data.keys()) == expected, f"missing: {expected - set(data.keys())}"
