"""Turn duration strings such as '1h30m' into a number of seconds.

Input rules: see docs/DECISIONS.md (D-3).
"""

from __future__ import annotations

import re

# Largest first; the order is also the order units must appear in a string.
UNITS: dict[str, int] = {"d": 86400, "h": 3600, "m": 60, "s": 1}

_TOKEN = re.compile(r"(\d+)([a-z])")


def _rank(unit: str) -> int:
    """Position of `unit` in UNITS, largest first; an unknown unit raises ValueError."""
    return list(UNITS).index(unit)


def _invalid(text: str, reason: str, index: int) -> ValueError:
    """The error for `text`, naming what went wrong and where, as a position in `text`."""
    return ValueError(f"invalid duration {text!r}: {reason} at position {index}")


def parse_duration(text: str) -> int:
    """Return the number of seconds in `text`, e.g. '1h30m' -> 5400.

    Surrounding whitespace is ignored and units are case-insensitive. Each unit may appear
    once, largest first. Anything else raises ValueError, whose message names the position in
    `text` where the input went wrong: "invalid duration '1h3x': unexpected 'x' at position 3".
    """
    cleaned = text.strip().lower()
    if not cleaned:
        raise ValueError(f"invalid duration {text!r}: empty")
    offset = len(text) - len(text.lstrip())  # positions count from the start of `text`
    total = 0
    pos = 0
    last_rank = -1
    for match in _TOKEN.finditer(cleaned):
        if match.start() != pos:
            raise _invalid(text, f"unexpected {text[offset + pos]!r}", offset + pos)
        amount, unit = match.groups()
        if unit not in UNITS:
            raise _invalid(text, f"unexpected {text[offset + match.start(2)]!r}",
                           offset + match.start(2))  # fmt: skip
        rank = _rank(unit)
        if rank <= last_rank:
            raise _invalid(text, f"unit {unit!r} out of order or repeated", offset + match.start(2))
        last_rank = rank
        total += int(amount) * UNITS[unit]
        pos = match.end()
    if pos != len(cleaned):
        raise _invalid(text, f"unexpected {text[offset + pos]!r}", offset + pos)
    return total
