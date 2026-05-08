"""Tests for shared metrics.jsonl reader (ADR-103, 0.7.1)."""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker._metrics_io import iter_recent_entries


def test_glob_orders_newest_first(tmp_path: Path) -> None:
    """Date-sharded files yield newest-first; legacy file trails."""
    obs = tmp_path / "obs"
    obs.mkdir()
    (obs / "metrics-2026-05-06.jsonl").write_text(
        json.dumps({"event": "post_tool_use", "tool_name": "old"}) + "\n",
    )
    (obs / "metrics-2026-05-08.jsonl").write_text(
        json.dumps({"event": "post_tool_use", "tool_name": "newer"}) + "\n",
    )
    (obs / "metrics-2026-05-07.jsonl").write_text(
        json.dumps({"event": "post_tool_use", "tool_name": "middle"}) + "\n",
    )
    names = [e["tool_name"] for e in iter_recent_entries(obs)]
    assert names == ["newer", "middle", "old"]


def test_legacy_file_appended_after_dated(tmp_path: Path) -> None:
    """Pre-0.7.1 ``metrics.jsonl`` is read AFTER all dated files (= treated
    as oldest data)."""
    obs = tmp_path / "obs"
    obs.mkdir()
    (obs / "metrics-2026-05-08.jsonl").write_text(
        json.dumps({"event": "post_tool_use", "tool_name": "dated"}) + "\n",
    )
    (obs / "metrics.jsonl").write_text(
        json.dumps({"event": "post_tool_use", "tool_name": "legacy"}) + "\n",
    )
    names = [e["tool_name"] for e in iter_recent_entries(obs)]
    assert names == ["dated", "legacy"]


def test_event_filter(tmp_path: Path) -> None:
    """The ``event`` parameter restricts yielded entries; pre-0.5.4 entries
    lacking the ``event`` tag default to ``post_tool_use``."""
    obs = tmp_path / "obs"
    obs.mkdir()
    (obs / "metrics-2026-05-08.jsonl").write_text(
        json.dumps({"event": "stop", "status": "completed"})
        + "\n"
        + json.dumps({"event": "post_tool_use", "tool_name": "a"})
        + "\n"
        + json.dumps({"tool_name": "implicit-pt"})
        + "\n",  # legacy tag absent
    )
    pt = list(iter_recent_entries(obs, event="post_tool_use"))
    assert {e.get("tool_name") for e in pt} == {"a", "implicit-pt"}
    stops = list(iter_recent_entries(obs, event="stop"))
    assert len(stops) == 1
    assert stops[0]["status"] == "completed"


def test_days_cap(tmp_path: Path) -> None:
    """``days`` parameter caps how many dated files are read."""
    obs = tmp_path / "obs"
    obs.mkdir()
    for date in ("2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05"):
        (obs / f"metrics-{date}.jsonl").write_text(
            json.dumps({"event": "post_tool_use", "date": date}) + "\n",
        )
    # days=2 reads only the 2 newest
    dates = [e["date"] for e in iter_recent_entries(obs, days=2)]
    assert dates == ["2026-05-05", "2026-05-04"]


def test_missing_dir_returns_empty(tmp_path: Path) -> None:
    assert list(iter_recent_entries(tmp_path / "nonexistent")) == []


def test_malformed_lines_skipped(tmp_path: Path) -> None:
    obs = tmp_path / "obs"
    obs.mkdir()
    (obs / "metrics-2026-05-08.jsonl").write_text(
        json.dumps({"event": "post_tool_use", "tool_name": "valid"})
        + "\n"
        + "not json\n"
        + "[]\n"  # parses as list, but not dict → skipped
        + json.dumps({"event": "post_tool_use", "tool_name": "after-bad"})
        + "\n",
    )
    names = [e["tool_name"] for e in iter_recent_entries(obs)]
    assert names == ["after-bad", "valid"]
