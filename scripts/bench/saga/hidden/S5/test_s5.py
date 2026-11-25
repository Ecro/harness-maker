"""S5 iCalendar export. The no-new-dependency goal is checked by the runner, not here."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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
    assert datetime(2026, 1, 5, 9, 0, tzinfo=UTC) in _starts(text)
    assert "SUMMARY:Dentist" in text


def _starts(text: str) -> list[datetime]:
    """Every DTSTART as an instant: UTC (`...Z`) or with a TZID; the prompt fixes neither."""
    found = []
    for params, value in re.findall(r"^DTSTART([^:\r\n]*):(\d{8}T\d{6}Z?)", text, re.M):
        when = datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S")
        zone = re.search(r"TZID=([^;:]+)", params)
        if value.endswith("Z"):
            found.append(when.replace(tzinfo=UTC))
        elif zone:
            found.append(when.replace(tzinfo=ZoneInfo(zone.group(1))).astimezone(UTC))
    return found
