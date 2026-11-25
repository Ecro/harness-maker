from __future__ import annotations

from datetime import UTC, datetime

from remind.fmt import format_due, format_line


def test_format_due() -> None:
    assert format_due(datetime(2026, 1, 5, 9, 0, tzinfo=UTC)) == "2026-01-05 09:00"


def test_format_line() -> None:
    line = format_line("ab12", datetime(2026, 1, 5, 9, 0, tzinfo=UTC), "Call")
    assert line.startswith("ab12  ")
    assert line.endswith("  Call")
