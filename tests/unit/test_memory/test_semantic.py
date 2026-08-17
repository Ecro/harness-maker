"""Tests for semantic memory layer."""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

import pytest

from harness_maker.memory.semantic import SemanticStore


def _semantic_worker(base_dir: str, worker_id: int, n: int) -> None:
    """Top-level worker for multiprocessing.Process — distinct slugs per writer."""
    store = SemanticStore(Path(base_dir))
    for i in range(n):
        store.write(
            slug=f"w{worker_id}-{i}",
            category="test",
            summary=f"summary-{worker_id}-{i}",
            keywords=[f"k{worker_id}"],
        )


def test_write_and_read(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    entry = store.write(
        slug="atomic-write",
        category="pattern",
        summary="Always use atomic_write for disk persistence",
        keywords=["file", "write", "atomic"],
    )
    assert entry["slug"] == "atomic-write"
    all_entries = store.read_all()
    assert len(all_entries) == 1


def test_deduplicates_by_slug(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    store.write(slug="x", category="a", summary="v1", keywords=["k1"])
    store.write(slug="x", category="a", summary="v2", keywords=["k2"])
    all_entries = store.read_all()
    assert len(all_entries) == 1
    assert all_entries[0]["summary"] == "v2"


def test_search_by_keyword(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    store.write(slug="auth", category="pattern", summary="Auth flow", keywords=["auth", "security"])
    store.write(slug="perf", category="pattern", summary="Perf tips", keywords=["performance"])
    results = store.search("auth")
    assert len(results) == 1
    assert results[0]["slug"] == "auth"


def test_search_by_summary(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    store.write(slug="x", category="a", summary="Use atomic_write everywhere", keywords=[])
    results = store.search("atomic")
    assert len(results) == 1


def test_search_case_insensitive(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    store.write(slug="x", category="a", summary="Test", keywords=["PyTest"])
    results = store.search("pytest")
    assert len(results) == 1


def test_empty_store_search(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    assert store.search("anything") == []


def test_write_many_single_lock_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Perf F6 (0.7.1): write_many acquires the lock exactly once for
    N entries instead of N times via repeated ``write`` calls."""
    import contextlib

    import harness_maker.memory.semantic as semantic_module
    from harness_maker.memory._locking import exclusive_lock

    real_lock = exclusive_lock
    acquire_count = 0

    @contextlib.contextmanager
    def counted_lock(path: Path):  # type: ignore[no-untyped-def]
        nonlocal acquire_count
        acquire_count += 1
        with real_lock(path):
            yield

    monkeypatch.setattr(semantic_module, "exclusive_lock", counted_lock)
    store = SemanticStore(tmp_path)
    entries = [
        {"slug": f"k{i}", "category": "test", "summary": str(i), "keywords": []} for i in range(100)
    ]
    written = store.write_many(entries)
    assert len(written) == 100
    assert acquire_count == 1, f"expected 1 lock acquire, got {acquire_count}"
    # All 100 entries must be persisted.
    all_entries = store.read_all()
    assert len(all_entries) == 100


def test_concurrent_set_no_lost_update(tmp_path: Path) -> None:
    """4 processes × 25 distinct slugs each: index must contain all 100 entries.

    Validates Phase 12a flock fix for the read-modify-replace lost-update race
    where two concurrent writers would clobber each other's updates.
    """
    n_per_worker = 25
    n_workers = 4
    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_semantic_worker, args=(str(tmp_path), wid, n_per_worker))
        for wid in range(n_workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert not p.is_alive(), "worker timed out"
        assert p.exitcode == 0, f"worker exited with {p.exitcode}"
    store = SemanticStore(tmp_path)
    entries = store.read_all()
    assert len(entries) == n_per_worker * n_workers, (
        f"expected {n_per_worker * n_workers} entries, got {len(entries)}"
    )
    slugs = {e["slug"] for e in entries}
    expected = {f"w{wid}-{i}" for wid in range(n_workers) for i in range(n_per_worker)}
    assert slugs == expected, f"missing: {expected - slugs}"
