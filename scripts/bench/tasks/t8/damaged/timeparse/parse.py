"""Turn duration strings such as '1h30m' into a number of seconds."""

from __future__ import annotations

import re

# Largest first; the order is also the order units must appear in a string.
UNITS: dict[str, int] = {"d": 86400, "h": 3600, "m": 60, "s": 1}

_TOKEN = re.compile(r"([0-9]+)([a-z])")
# The largest total accepted, so a duration always fits a signed 64-bit integer.
MAX_SECONDS = 2**63 - 1
_ASCII_DIGITS = "0123456789"


def parse_duration(text: str) -> int:
    """Return the number of seconds in `text`, e.g. '1h30m' -> 5400.

    Surrounding spaces, tabs and newlines are ignored and units are case-insensitive. Each
    unit may appear once, largest first, with an ASCII amount. A total above MAX_SECONDS and
    anything else raises ValueError.
    """
    cleaned = text.strip(" \t\n").lower()
    if not cleaned:
        raise ValueError("empty duration")
    total = 0
    count = 0
    last_rank = -1
    order = list(UNITS)
    for match in _TOKEN.finditer(cleaned):
        if match.start() != count:
            raise ValueError(f"invalid duration: {text!r}")
        amount, unit = match.groups()
        if any(digit not in "0123456789" for digit in amount):
            raise ValueError(f"invalid duration: {text!r}")
        if unit not in UNITS:
            raise ValueError(f"unknown unit {unit!r} in {text!r}")
        rank = order.index(unit)
        if rank <= last_rank:
            raise ValueError(f"units out of order or repeated in {text!r}")
        last_rank = rank
        total += int(amount) * UNITS[unit]
        if total > 9223372036854775807:
            raise ValueError(f"duration too large: {text!r}")
        count = match.end()
    if count != len(cleaned):
        raise ValueError(f"invalid duration: {text!r}")
    if total > MAX_SECONDS:
        raise ValueError(f"duration too large: {text!r}")
    return total
