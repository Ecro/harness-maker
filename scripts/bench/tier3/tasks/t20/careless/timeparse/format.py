"""Turn a number of seconds back into a duration string, compact or long."""

from __future__ import annotations

from timeparse.locale import unit_name
from timeparse.parse import UNITS


def format_duration(seconds: int, style: str = "compact", lang: str = "en") -> str:
    """Return `seconds` as '1h30m' (compact) or '1 hour, 30 minutes' (long, in `lang`)."""
    if style not in ("compact", "long"):
        raise ValueError(f"unknown style {style!r}")
    if seconds < 0:
        raise ValueError("negative duration")
    if seconds == 0:
        return "0s" if style == "compact" else "0 seconds"
    parts: list[str] = []
    remaining = seconds
    for unit, size in UNITS.items():
        count, remaining = divmod(remaining, size)
        if count:
            parts.append(f"{count}{unit}" if style == "compact" else unit_name(unit, count, lang))
    return "".join(parts) if style == "compact" else ", ".join(parts)
