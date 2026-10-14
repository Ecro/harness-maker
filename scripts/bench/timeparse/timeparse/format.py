"""Turn a number of seconds back into a compact duration string."""

from __future__ import annotations

from timeparse.parse import UNITS


def format_duration(seconds: int) -> str:
    """Return the compact form of `seconds`, e.g. 5400 -> '1h30m', 0 -> '0s'.

    Zero units are left out. Negative input raises ValueError.
    """
    if seconds < 0:
        raise ValueError("negative duration")
    if seconds == 0:
        return "0s"
    parts: list[str] = []
    remaining = seconds
    for unit, size in UNITS.items():
        count, remaining = divmod(remaining, size)
        if count:
            parts.append(f"{count}{unit}")
    return "".join(parts)
