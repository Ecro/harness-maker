"""S5 iCalendar export. The no-new-dependency goal is checked by the runner, not here."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from remind import api
from remind.cli import main


def test_export_ics(save_file: Path, tmp_path: Path) -> None:
    api.add("Rent", datetime(2026, 1, 5, 9, 0, tzinfo=UTC))
    api.add("Dentist", datetime(2026, 2, 3, 14, 30, tzinfo=UTC))
    out = tmp_path / "out.ics"
    assert main(["export", str(out), "--format", "ics"]) == 0
    text = out.read_text()
    assert text.lstrip().startswith("BEGIN:VCALENDAR")
    assert text.rstrip().endswith("END:VCALENDAR")
    assert text.count("BEGIN:VEVENT") == 2
    assert "DTSTART:20260105T090000Z" in text
    assert "SUMMARY:Dentist" in text
