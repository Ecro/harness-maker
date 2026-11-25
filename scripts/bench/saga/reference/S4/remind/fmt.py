"""Human-readable output."""

from __future__ import annotations

from datetime import datetime

from remind import config


def format_due(when: datetime) -> str:
    """A due time in the configured zone, else the machine's local time zone."""
    return when.astimezone(config.zone()).strftime("%Y-%m-%d %H:%M")


def format_line(ident: str, when: datetime, text: str) -> str:
    return f"{ident}  {format_due(when)}  {text}"
