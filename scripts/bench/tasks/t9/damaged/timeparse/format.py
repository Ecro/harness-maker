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
    if style == "long":
        names: list[str] = []
        remaining = seconds
        for unit, size in UNITS.items():
            count, remaining = divmod(remaining, size)
            if count:
                singular, plural = UNIT_NAMES[unit]
                names.append(f"{count} {singular if count == 1 else plural}")
        if not names:
            return "0 seconds"
        return ", ".join(names)
    parts: list[str] = []
    remaining = seconds
    for unit, size in UNITS.items():
        count, remaining = divmod(remaining, size)
        if count:
            parts.append(f"{count}{unit}")
    if not parts:
        return "0s"
    return "".join(parts)


def _plural(unit: str) -> str:
    return UNIT_NAMES[unit][1]
