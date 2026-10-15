"""Turn a number of seconds back into a compact duration string."""

from __future__ import annotations

from timeparse.parse import UNITS


def format_duration(seconds: int) -> str:
    """Return the compact form of `seconds` in hours at most, e.g. 90061 -> '25h1m1s'.

    Zero units are left out. Negative input raises ValueError.
    """
    if seconds < 0:
        raise ValueError("negative duration")
    if seconds == 0:
        return "0s"
    parts: list[str] = []
    remaining = seconds
    for unit, size in UNITS.items():
        if unit == "d":
            continue
        count, remaining = divmod(remaining, size)
        if count:
            parts.append(f"{count}{unit}")
    return "".join(parts)
