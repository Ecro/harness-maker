"""Turn duration strings such as '1h30m' into a number of seconds.

Input rules: see docs/DECISIONS.md (D-3).
"""

from __future__ import annotations

import re
from decimal import Decimal

# Largest first; the order is also the order units must appear in a string.
UNITS: dict[str, int] = {"d": 86400, "h": 3600, "m": 60, "s": 1}

_TOKEN = re.compile(r"(\d+)([a-z])")  # whole amounts only: timeparse.strict reads it
# An amount may be a decimal, written <digits>.<digits> (D-3).
_AMOUNT_TOKEN = re.compile(r"(\d+(?:\.\d+)?)([a-z])")


def _rank(unit: str) -> int:
    """Position of `unit` in UNITS, largest first; an unknown unit raises ValueError."""
    return list(UNITS).index(unit)


def parse_duration(text: str) -> int:
    """Return the number of seconds in `text`, e.g. '1h30m' -> 5400, '1.5h' -> 5400.

    Surrounding whitespace is ignored and units are case-insensitive. Each unit may appear
    once, largest first. An amount may be a decimal, but the total must be whole seconds
    (D-3): '1.5s' raises. Anything else raises ValueError.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        raise ValueError("empty duration")
    total = 0
    pos = 0
    last_rank = -1
    for match in _AMOUNT_TOKEN.finditer(cleaned):
        if match.start() != pos:
            raise ValueError(f"invalid duration: {text!r}")
        amount, unit = match.groups()
        if unit not in UNITS:
            raise ValueError(f"unknown unit {unit!r} in {text!r}")
        rank = _rank(unit)
        if rank <= last_rank:
            raise ValueError(f"units out of order or repeated in {text!r}")
        last_rank = rank
        seconds = Decimal(amount) * UNITS[unit]
        if seconds != seconds.to_integral_value():
            raise ValueError(f"not a whole number of seconds: {text!r}")
        total += int(seconds)
        pos = match.end()
    if pos != len(cleaned):
        raise ValueError(f"invalid duration: {text!r}")
    return total
