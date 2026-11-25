"""The reminder record."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Reminder:
    id: str
    text: str
    due: datetime  # always timezone-aware, UTC
    done: bool = False
