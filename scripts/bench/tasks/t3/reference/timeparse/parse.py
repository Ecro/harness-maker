"""Turn duration strings such as '1h30m' into a number of seconds."""

from __future__ import annotations

import re

# Largest first; the order is also the order units must appear in a string.
UNITS: dict[str, int] = {"d": 86400, "h": 3600, "m": 60, "s": 1}

_TOKEN = re.compile(r"(\d+)([a-z])")
_ISO = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?")


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


def parse_iso_duration(text: str) -> int:
    """Return the seconds in an ISO-8601 day/time duration such as 'P1DT2H'."""
    cleaned = text.strip()
    match = _ISO.fullmatch(cleaned)
    if match is None or cleaned in ("P", "PT") or cleaned.endswith("T"):
        raise ValueError(f"invalid ISO-8601 duration: {text!r}")
    days, hours, minutes, secs = (int(g) if g is not None else 0 for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + secs
