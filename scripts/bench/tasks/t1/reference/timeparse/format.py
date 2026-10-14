"""Turn a number of seconds back into a compact duration string."""

from __future__ import annotations

from timeparse.parse import UNITS


def format_duration(seconds: int, max_units: int | None = None) -> str:
    """Return the compact form of `seconds`, e.g. 5400 -> '1h30m', 0 -> '0s'.

    Zero units are left out. Negative input raises ValueError. `max_units` keeps that many
    positions from the largest non-zero unit and rounds the rest half-up into the last one.
    """
    if seconds < 0:
        raise ValueError("negative duration")
    if max_units is not None and max_units < 1:
        raise ValueError("max_units must be at least 1")
    if seconds == 0:
        return "0s"
    sizes = list(UNITS.values())
    if max_units is not None:
        first = next(i for i, size in enumerate(sizes) if seconds >= size)
        step = sizes[min(first + max_units, len(sizes)) - 1]
        count, rest = divmod(seconds, step)
        if 2 * rest >= step:
            count += 1
        seconds = count * step
    parts: list[str] = []
    remaining = seconds
    for unit, size in UNITS.items():
        count, remaining = divmod(remaining, size)
        if count:
            parts.append(f"{count}{unit}")
    return "".join(parts)
