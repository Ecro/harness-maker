"""iCalendar (RFC 5545) output, standard library only."""

from __future__ import annotations

from datetime import datetime


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", r"\;").replace(",", "\\,").replace("\n", "\\n")


def calendar(rows: list[tuple[datetime, str, str]]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//remind//EN"]
    for due, text, ident in rows:
        stamp = due.strftime("%Y%m%dT%H%M%SZ")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{ident}-{stamp}@remind",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{stamp}",
            f"SUMMARY:{_escape(text)}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
