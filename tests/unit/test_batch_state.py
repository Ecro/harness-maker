"""Tests for spec_inventory.batch_state (P1, ADR-013 R2)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness_maker.spec_inventory.batch_state import BatchSpecState


def test_initialize_empty(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    bs = BatchSpecState(p, batch_number=1)
    assert bs.batch_number == 1
    assert bs.next_batch_queue() == []
    assert bs.current_progress()["queued"] == 0


def test_add_features_persists_yaml(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    bs = BatchSpecState(p, batch_number=1)
    bs.add_features(["render", "cache", "interview"])
    assert p.exists()
    raw = yaml.safe_load(p.read_text())
    ids = [e["feature_id"] for e in raw["entries"]]
    assert ids == ["render", "cache", "interview"]


def test_add_features_idempotent(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    bs = BatchSpecState(p, batch_number=1)
    bs.add_features(["render"])
    bs.add_features(["render", "cache"])  # render dedup'd
    assert len(bs.next_batch_queue()) == 2


def test_mark_in_progress_and_complete(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    bs = BatchSpecState(p, batch_number=1)
    bs.add_features(["render"])
    bs.mark_in_progress("render", at_iso="2026-05-20T12:00:00Z")
    assert bs.current_progress()["in_progress"] == 1
    bs.mark_complete("render", at_iso="2026-05-20T12:05:00Z", note="ok")
    assert bs.current_progress()["complete"] == 1
    assert bs.current_progress()["queued"] == 0


def test_mark_failed_records_note(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    bs = BatchSpecState(p, batch_number=1)
    bs.add_features(["render"])
    bs.mark_failed("render", note="spec_quality below 85")
    counts = bs.current_progress()
    assert counts["failed"] == 1


def test_unknown_feature_raises(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    bs = BatchSpecState(p, batch_number=1)
    with pytest.raises(KeyError):
        bs.mark_complete("not-added")


def test_round_trip_via_reload(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    bs = BatchSpecState(p, batch_number=2)
    bs.add_features(["render", "cache"])
    bs.mark_complete("render")

    bs2 = BatchSpecState(p)  # reload
    assert bs2.batch_number == 2
    progress = bs2.current_progress()
    assert progress["complete"] == 1
    assert progress["queued"] == 1


def test_next_batch_queue_limit(tmp_path: Path) -> None:
    p = tmp_path / "state.yaml"
    bs = BatchSpecState(p, batch_number=1)
    bs.add_features([f"feat-{i}" for i in range(10)])
    queue = bs.next_batch_queue(limit=3)
    assert len(queue) == 3
    assert queue[0].feature_id == "feat-0"
