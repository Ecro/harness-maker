"""Read and write the save file (format v1).

A v1 file is a JSON object: {"version": 1, "reminders": [entry, ...]}. Each entry has
"id", "text", "due" (UTC, ISO 8601 with a trailing "Z") and "done"; a repeating reminder adds
"every" and "count".
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from remind.migrate import migrate_v0
from remind.model import Reminder

VERSION = 1


def to_iso(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _entry(reminder: Reminder) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": reminder.id,
        "text": reminder.text,
        "due": to_iso(reminder.due),
        "done": reminder.done,
    }
    if reminder.every is not None:
        entry |= {"every": reminder.every, "count": reminder.count}
    return entry


def _reminder(entry: dict[str, Any]) -> Reminder:
    return Reminder(
        id=entry["id"],
        text=entry["text"],
        due=from_iso(entry["due"]),
        done=bool(entry.get("done", False)),
        every=entry.get("every"),
        count=int(entry.get("count", 1)),
    )


def read_entries(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):  # a file written before v1
        data = migrate_v0(data)
    if data.get("version") != VERSION:
        raise ValueError(f"unsupported save file version: {data.get('version')!r}")
    entries: list[dict[str, Any]] = data["reminders"]
    return entries


def load(path: Path) -> list[Reminder]:
    if not path.exists():
        return []
    return [_reminder(entry) for entry in read_entries(path)]


def save(path: Path, reminders: list[Reminder]) -> None:
    data = {"version": VERSION, "reminders": [_entry(r) for r in reminders]}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
