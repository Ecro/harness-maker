"""Tests for episodic memory layer."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from harness_maker.memory.episodic import EpisodicStore


def test_write_and_read(tmp_path: Path) -> None:
    store = EpisodicStore(tmp_path)
    ts = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)
    event = store.write(
        session_id="s1", stage="execute", payload={"action": "edit"}, timestamp=ts
    )
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
