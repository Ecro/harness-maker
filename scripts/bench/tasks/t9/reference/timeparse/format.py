"""Turn a number of seconds back into a duration string, compact or long."""

from __future__ import annotations

from timeparse.parse import UNITS

# Singular and plural name of each unit in UNITS, for the long style.
UNIT_NAMES: dict[str, tuple[str, str]] = {
    "d": ("day", "days"),
    "h": ("hour", "hours"),
    "m": ("minute", "minutes"),
    "s": ("second", "seconds"),
}
STYLES = ("compact", "long")


def format_duration(seconds: int, style: str = "compact") -> str:
    """Return `seconds` as text, e.g. 5400 -> '1h30m' or, long, '1 hour, 30 minutes'.

    Zero units are left out. Negative input or an unknown style raises ValueError.
    """
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}")
    if seconds < 0:
        raise ValueError("negative duration")
    counts = _unit_counts(seconds)
    if style == "long":
        if not counts:
            return "0 seconds"
        return ", ".join(f"{count} {_name(unit, count)}" for unit, count in counts)
    if not counts:
        return "0s"
    return "".join(f"{count}{unit}" for unit, count in counts)


def _unit_counts(seconds: int) -> list[tuple[str, int]]:
    """The non-zero (unit, count) pairs of `seconds`, largest unit first."""
    counts: list[tuple[str, int]] = []
    remaining = seconds
    for unit, size in UNITS.items():
        count, remaining = divmod(remaining, size)
        if count:
            counts.append((unit, count))
    return counts


def _name(unit: str, count: int) -> str:
    singular, plural = UNIT_NAMES[unit]
    return singular if count == 1 else plural
