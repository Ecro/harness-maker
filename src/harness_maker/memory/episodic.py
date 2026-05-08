"""Episodic memory layer — raw event JSONL store with neighbor expansion retrieval."""

from __future__ import annotations

import json
import os
import tempfile
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
        """Append an event and return it."""
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
        fd, tmp = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        try:
            line = json.dumps(event, ensure_ascii=False) + "\n"
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                existing = ""
                if target.exists():
                    existing = target.read_text(encoding="utf-8")
                f.write(existing + line)
            os.replace(tmp, target)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
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

    def read_all(self) -> list[dict[str, Any]]:
        """Read all events across all dates, chronologically."""
        all_events: list[dict[str, Any]] = []
        for f in sorted(self._dir.glob("*.jsonl")):
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
