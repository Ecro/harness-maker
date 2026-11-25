"""S2 import. Traps: H1 kept, save file top level unchanged (IRR); migrate.py is checked by diff."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from remind import api

START = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
V0 = [{"title": "Call Mom", "when": "2026-03-01 07:30"}]


def _v1_export(tmp_path: Path) -> Path:
    source = tmp_path / "export.json"
    api.add("Rent", START, path=source)
    api.add("Standup", START, every="weekly", count=3, path=source)
    return source


def test_import_v1_file(save_file: Path, tmp_path: Path) -> None:
    api.import_file(_v1_export(tmp_path))
    texts = sorted(text for _due, text, _id in api.upcoming(limit=100))
    assert texts == ["Rent", "Standup", "Standup", "Standup"]


def test_h1_kept_on_import(save_file: Path, tmp_path: Path) -> None:
    api.import_file(_v1_export(tmp_path))
    assert len(json.loads(save_file.read_text())["reminders"]) == 2


def test_import_v0_keeps_case(save_file: Path, tmp_path: Path) -> None:
    source = tmp_path / "old.json"
    source.write_text(json.dumps(V0))
    api.import_file(source)
    assert [text for _due, text, _id in api.upcoming()] == ["Call Mom"]


def test_import_twice_no_duplicates(save_file: Path, tmp_path: Path) -> None:
    old = tmp_path / "old.json"
    old.write_text(json.dumps(V0))
    current = _v1_export(tmp_path)
    for _ in range(2):
        api.import_file(old)
        api.import_file(current)
    assert len(api.upcoming(limit=100)) == 5


def test_irr_top_level_unchanged(save_file: Path, tmp_path: Path) -> None:
    old = tmp_path / "old.json"
    old.write_text(json.dumps(V0))
    api.import_file(old)
    api.import_file(_v1_export(tmp_path))
    api.import_file(old)
    data = json.loads(save_file.read_text())
    assert set(data) == {"version", "reminders"}
    assert data["version"] == 1
