"""Episodic memory layer — raw event JSONL store with neighbor expansion retrieval."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class EpisodicStore:
    """Append-only JSONL store for raw session events.

    Each event carries a timestamp, session_id, stage, and arbitrary payload.
    Retrieval supports neighbor expansion: given an event index, return the
    surrounding N events for context reconstruction.
    """

    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir / "episodic"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _file_for_date(self, date_str: str) -> Path:
        return self._dir / f"{date_str}.jsonl"

    def write(
        self,
        *,
        session_id: str,
        stage: str,
        payload: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Append an event and return it.

        Uses POSIX ``O_APPEND`` + a single ``os.write(fd, bytes)`` so the
        syscall is atomic when the encoded line ≤ ``PIPE_BUF`` (4 KiB on
        Linux). Round-2 Conc F1: this bypasses Python's TextIOWrapper
        buffer, which could otherwise split a ``f.write`` into multiple
        ``write(2)`` syscalls for larger lines and silently invalidate the
        atomicity guarantee under concurrent writers.
        """
        ts = timestamp or datetime.now(UTC)
        event: dict[str, Any] = {
            "timestamp": ts.isoformat(),
            "session_id": session_id,
            "stage": stage,
            **payload,
        }
        date_str = ts.strftime("%Y-%m-%d")
        target = self._file_for_date(date_str)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(str(target), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)
        return event

    def read(self, date_str: str) -> list[dict[str, Any]]:
        """Read all events for a given date."""
        target = self._file_for_date(date_str)
        if not target.is_file():
            return []
        events: list[dict[str, Any]] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
        return events

    def read_all(self, max_days: int | None = 30) -> list[dict[str, Any]]:
        """Read events across recent date files, chronologically.

        0.7.1 (Perf F7): ``max_days`` (default 30) caps the window so a
        long-lived store does not load every historical day into memory
        on every call. Pass ``None`` for the pre-0.7.1 unbounded behaviour
        when a caller genuinely wants the full history.
        """
        files = sorted(self._dir.glob("*.jsonl"))
        if max_days is not None:
            files = files[-max_days:]
        all_events: list[dict[str, Any]] = []
        for f in files:
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    all_events.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
        return all_events

    def retrieve_neighbors(
        self,
        date_str: str,
        index: int,
        window: int = 3,
    ) -> list[dict[str, Any]]:
        """Return events[index-window : index+window+1] for context expansion."""
        events = self.read(date_str)
        start = max(0, index - window)
        end = min(len(events), index + window + 1)
        return events[start:end]
