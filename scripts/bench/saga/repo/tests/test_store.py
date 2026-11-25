from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from remind import store
from remind.model import Reminder


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "r.json"
    reminder = Reminder("a1", "Pay rent", datetime(2026, 2, 1, 8, 0, tzinfo=UTC))
    store.save(path, [reminder])
    assert store.load(path) == [reminder]
    data = json.loads(path.read_text())
    assert data == {
        "version": 1,
        "reminders": [
            {"id": "a1", "text": "Pay rent", "due": "2026-02-01T08:00:00Z", "done": False}
        ],
    }


def test_missing_file_is_empty(tmp_path: Path) -> None:
    assert store.load(tmp_path / "none.json") == []


def test_v0_file_is_migrated(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps([{"title": "water plants", "when": "2026-03-01 07:30"}]))
    [reminder] = store.load(path)
    assert reminder.text == "water plants"
    assert reminder.due == datetime(2026, 3, 1, 7, 30, tzinfo=UTC)
