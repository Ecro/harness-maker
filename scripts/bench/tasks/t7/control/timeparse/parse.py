"""Turn duration strings such as '1h30m' into a number of seconds."""

from __future__ import annotations

import re

# Largest first; the order is also the order units must appear in a string. Weeks come first,
# so format_duration uses them as its largest unit and "1d1w" is out of order.
UNITS: dict[str, int] = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}

_TOKEN = re.compile(r"(\d+)([a-z])")


def parse_duration(text: str) -> int:
    """Return the number of seconds in `text`, e.g. '1h30m' -> 5400.

    Surrounding whitespace is ignored and units are case-insensitive. Each unit may appear
    once, largest first. Anything else raises ValueError.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        raise ValueError("empty duration")
    total = 0
    pos = 0
    last_rank = -1
    order = list(UNITS)
    for match in _TOKEN.finditer(cleaned):
        if match.start() != pos:
            raise ValueError(f"invalid duration: {text!r}")
        amount, unit = match.groups()
        if unit not in UNITS:
            raise ValueError(f"unknown unit {unit!r} in {text!r}")
        rank = order.index(unit)
        if rank <= last_rank:
            raise ValueError(f"units out of order or repeated in {text!r}")
        last_rank = rank
        total += int(amount) * UNITS[unit]
        pos = match.end()
    if pos != len(cleaned):
        raise ValueError(f"invalid duration: {text!r}")
    return total
