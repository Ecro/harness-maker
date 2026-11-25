"""The reminder record."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

STEPS = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1)}
MAX_COUNT = 52


@dataclass
class Reminder:
    id: str
    text: str
    due: datetime  # always timezone-aware, UTC
    done: bool = False
    every: str | None = None  # "daily" or "weekly"; one entry stands for every occurrence
    count: int = 1

    def occurrences(self) -> list[datetime]:
        if self.every is None:
            return [self.due]
        return [self.due + STEPS[self.every] * n for n in range(self.count)]
