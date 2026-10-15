"""Turn a number of seconds back into a compact duration string."""

from __future__ import annotations

from timeparse.parse import UNITS

WEEK = 7 * 24 * 60 * 60
DAYS_PER_WEEK = 7


def format_duration(seconds: int) -> str:
    """Return the compact form of `seconds`, e.g. 5400 -> '1h30m', 0 -> '0s'.

    Zero units are left out. Negative input raises ValueError.
    """
    if seconds < 0:
        raise ValueError("negative duration")
    if seconds == 0:
        return "0s"
    parts: list[str] = []
    weeks, days_left = divmod(seconds, WEEK)
    if weeks:
        parts.append(f"{weeks}w")
    for unit, size in UNITS.items():
        if unit == "w":
            continue
        count, days_left = divmod(days_left, size)
        if count:
            parts.append(f"{count}{unit}")
    return "".join(parts)
