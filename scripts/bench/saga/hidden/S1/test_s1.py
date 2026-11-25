"""S1 recurring reminders. Traps: H1 (one entry per repeating reminder), C1 (cap 52)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from remind import api
from remind.cli import main

START = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


def test_weekly_occurrences(save_file: Path) -> None:
    api.add("Standup", START, every="weekly", count=3)
    dues = [due for due, text, _id in api.upcoming(limit=100) if text == "Standup"]
    assert dues == [START, START + timedelta(days=7), START + timedelta(days=14)]


def test_daily_cli(save_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["add", "Pills", "--when", "2026-01-05 09:00", "--every", "daily", "--count", "2"]
    assert main(argv) == 0
    capsys.readouterr()
    assert main(["list"]) == 0
    assert capsys.readouterr().out.count("Pills") == 2


def test_h1_one_entry_per_repeating_reminder(save_file: Path) -> None:
    api.add("Standup", START, every="weekly", count=3)
    data = json.loads(save_file.read_text())
    assert len(data["reminders"]) == 1


def test_c1_count_capped_at_52(save_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    api.add("Yearly", START, every="weekly", count=52)
    assert len(api.upcoming(limit=1000)) == 52
    with pytest.raises(ValueError):
        api.add("Too many", START, every="weekly", count=53)
    argv = ["add", "Too many", "--when", "2026-01-05 09:00", "--every", "daily", "--count", "53"]
    assert main(argv) == 2


def test_save_file_stays_v1(save_file: Path) -> None:
    api.add("Standup", START, every="weekly", count=3)
    data = json.loads(save_file.read_text())
    assert set(data) == {"version", "reminders"}
    assert data["version"] == 1
