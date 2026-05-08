"""Tests for episodic memory layer."""

from __future__ import annotations

import multiprocessing as mp
from datetime import UTC, datetime
from pathlib import Path

from harness_maker.memory.episodic import EpisodicStore


def _episodic_worker(base_dir: str, worker_id: int, n: int) -> None:
    """Top-level worker for multiprocessing.Process — must be picklable."""
    store = EpisodicStore(Path(base_dir))
    ts = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)
    for i in range(n):
        store.write(
            session_id=f"w{worker_id}",
            stage="execute",
            payload={"worker_id": worker_id, "i": i},
            timestamp=ts,
        )


def test_write_and_read(tmp_path: Path) -> None:
    store = EpisodicStore(tmp_path)
    ts = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)
    event = store.write(session_id="s1", stage="execute", payload={"action": "edit"}, timestamp=ts)
    assert event["session_id"] == "s1"
    assert event["stage"] == "execute"
    events = store.read("2026-05-08")
    assert len(events) == 1
    assert events[0]["action"] == "edit"


def test_multiple_writes_append(tmp_path: Path) -> None:
    store = EpisodicStore(tmp_path)
    ts1 = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)
    ts2 = datetime(2026, 5, 8, 12, 1, 0, tzinfo=UTC)
    store.write(session_id="s1", stage="execute", payload={"n": 1}, timestamp=ts1)
    store.write(session_id="s1", stage="review", payload={"n": 2}, timestamp=ts2)
    events = store.read("2026-05-08")
    assert len(events) == 2


def test_read_nonexistent_date_returns_empty(tmp_path: Path) -> None:
    store = EpisodicStore(tmp_path)
    assert store.read("2099-01-01") == []


def test_retrieve_neighbors(tmp_path: Path) -> None:
    store = EpisodicStore(tmp_path)
    ts_base = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)
    from datetime import timedelta

    for i in range(10):
        store.write(
            session_id="s1",
            stage=f"stage-{i}",
            payload={"idx": i},
            timestamp=ts_base + timedelta(minutes=i),
        )
    neighbors = store.retrieve_neighbors("2026-05-08", index=5, window=2)
    assert len(neighbors) == 5
    assert neighbors[0]["idx"] == 3
    assert neighbors[-1]["idx"] == 7


def test_retrieve_neighbors_at_start(tmp_path: Path) -> None:
    store = EpisodicStore(tmp_path)
    ts = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)
    from datetime import timedelta

    for i in range(5):
        store.write(
            session_id="s1",
            stage=f"s{i}",
            payload={"idx": i},
            timestamp=ts + timedelta(minutes=i),
        )
    neighbors = store.retrieve_neighbors("2026-05-08", index=0, window=2)
    assert len(neighbors) == 3
    assert neighbors[0]["idx"] == 0


def test_read_all_across_dates(tmp_path: Path) -> None:
    store = EpisodicStore(tmp_path)
    ts1 = datetime(2026, 5, 7, 12, 0, 0, tzinfo=UTC)
    ts2 = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)
    store.write(session_id="s1", stage="a", payload={"day": 7}, timestamp=ts1)
    store.write(session_id="s2", stage="b", payload={"day": 8}, timestamp=ts2)
    all_events = store.read_all()
    assert len(all_events) == 2
    assert all_events[0]["day"] == 7
    assert all_events[1]["day"] == 8


def test_concurrent_append_no_loss(tmp_path: Path) -> None:
    """4 processes × 50 writes: file must contain exactly 200 events.

    Validates Phase 12a fix for the read-modify-replace race that previously
    caused episodic events to be silently dropped under concurrent hook fires.
    """
    n_per_worker = 50
    n_workers = 4
    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_episodic_worker, args=(str(tmp_path), wid, n_per_worker))
        for wid in range(n_workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0, f"worker exited with {p.exitcode}"
    store = EpisodicStore(tmp_path)
    events = store.read("2026-05-08")
    assert len(events) == n_per_worker * n_workers, (
        f"expected {n_per_worker * n_workers} events, got {len(events)}"
    )
    by_worker: dict[int, list[int]] = {}
    for ev in events:
        by_worker.setdefault(ev["worker_id"], []).append(ev["i"])
    for wid in range(n_workers):
        assert sorted(by_worker[wid]) == list(range(n_per_worker)), (
            f"worker {wid} missing entries: {sorted(by_worker[wid])}"
        )
