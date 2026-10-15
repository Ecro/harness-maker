"""Turn duration strings such as '1h30m' into a number of seconds.

Input rules: see docs/DECISIONS.md (D-3).
"""

from __future__ import annotations

import re

# Largest first; the order is also the order units must appear in a string.
UNITS: dict[str, int] = {"d": 86400, "h": 3600, "m": 60, "s": 1}

# One optional `<digits><unit>` group per unit, in UNITS order: each unit once, largest first.
_DURATION = re.compile("".join(rf"(?:(\d+){unit})?" for unit in UNITS))


def parse_duration(text: str) -> int:
    """Return the number of seconds in `text`, e.g. '1h30m' -> 5400.

    Surrounding whitespace is ignored and units are case-insensitive. Each unit may appear
    once, largest first. Anything else raises ValueError.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        raise ValueError("empty duration")
    match = _DURATION.fullmatch(cleaned)
    if match is None:
        raise ValueError(f"invalid duration: {text!r}")
    return sum(
        int(amount) * size
        for amount, size in zip(match.groups(), UNITS.values(), strict=True)
        if amount
    )
