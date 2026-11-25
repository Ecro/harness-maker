"""The public Python API. Every function takes an optional save-file path (default: config)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from remind import config, store
from remind.model import MAX_COUNT, STEPS, Reminder


def _path(path: Path | None) -> Path:
    return path if path is not None else config.save_file()


def parse_when(text: str) -> datetime:
    """'YYYY-MM-DD HH:MM' in UTC."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def add(
    text: str,
    due: datetime,
    *,
    every: str | None = None,
    count: int | None = None,
    path: Path | None = None,
) -> Reminder:
    if not text.strip():
        raise ValueError("reminder text is empty")
    if due.tzinfo is None:
        raise ValueError("due must be timezone-aware")
    if every is not None and every not in STEPS:
        raise ValueError(f"every must be one of {sorted(STEPS)}")
    total = 1 if every is None else (count or 1)
    if not 1 <= total <= MAX_COUNT:
        raise ValueError(f"count must be between 1 and {MAX_COUNT}")
    target = _path(path)
    reminders = store.load(target)
    reminder = Reminder(
        id=uuid.uuid4().hex[:8],
        text=text.strip(),
        due=due.astimezone(UTC),
        every=every,
        count=total,
    )
    reminders.append(reminder)
    store.save(target, reminders)
    return reminder


def upcoming(limit: int = 10, *, path: Path | None = None) -> list[tuple[datetime, str, str]]:
    """(due, text, id) of every open occurrence, earliest first."""
    rows = [
        (when, r.text, r.id)
        for r in store.load(_path(path))
        if not r.done
        for when in r.occurrences()
    ]
    rows.sort(key=lambda row: row[0])
    return rows[:limit]


def done(ident: str, *, path: Path | None = None) -> None:
    target = _path(path)
    reminders = store.load(target)
    for reminder in reminders:
        if reminder.id == ident:
            reminder.done = True
            store.save(target, reminders)
            return
    raise KeyError(ident)
