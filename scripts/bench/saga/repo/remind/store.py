"""Read and write the save file (format v1).

A v1 file is a JSON object: {"version": 1, "reminders": [entry, ...]}. Each entry has
"id", "text", "due" (UTC, ISO 8601 with a trailing "Z") and "done".
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
    return {
        "id": reminder.id,
        "text": reminder.text,
        "due": to_iso(reminder.due),
        "done": reminder.done,
    }


def _reminder(entry: dict[str, Any]) -> Reminder:
    return Reminder(
        id=entry["id"],
        text=entry["text"],
        due=from_iso(entry["due"]),
        done=bool(entry.get("done", False)),
    )


def load(path: Path) -> list[Reminder]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):  # a file written before v1
        data = migrate_v0(data)
    if data.get("version") != VERSION:
        raise ValueError(f"unsupported save file version: {data.get('version')!r}")
    return [_reminder(entry) for entry in data["reminders"]]


def save(path: Path, reminders: list[Reminder]) -> None:
    data = {"version": VERSION, "reminders": [_entry(r) for r in reminders]}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
