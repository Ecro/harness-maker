"""Turn a number of seconds back into a duration string, compact or long."""

from __future__ import annotations

from timeparse import locale
from timeparse.parse import UNITS

STYLES = ("compact", "long")
# How the long style joins its units, per language; names come from timeparse.locale.
JOINERS = {"en": ", ", "ko": " "}


def format_duration(seconds: int, style: str = "compact", lang: str = "en") -> str:
    """Return `seconds` as a duration string.

    compact (the default): 5400 -> '1h30m', 0 -> '0s'. long: 5400 -> '1 hour, 30 minutes',
    0 -> '0 seconds'; with lang="ko", 5400 -> '1시간 30분'. Zero units are left out. A negative
    number, another style or an unknown lang raises ValueError.
    """
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}")
    if style == "long" and lang not in JOINERS:
        raise ValueError(f"unknown lang {lang!r}")
    if seconds < 0:
        raise ValueError("negative duration")
    counts: list[tuple[str, int]] = []
    remaining = seconds
    for unit, size in UNITS.items():
        count, remaining = divmod(remaining, size)
        if count:
            counts.append((unit, count))
    if style == "compact":
        return "".join(f"{count}{unit}" for unit, count in counts) or "0s"
    if not counts:
        counts = [("s", 0)]
    return JOINERS[lang].join(locale.unit_name(unit, count, lang) for unit, count in counts)
