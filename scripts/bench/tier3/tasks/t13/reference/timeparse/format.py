"""Turn a number of seconds back into a compact duration string."""

from __future__ import annotations

from timeparse.parse import UNITS

# D-6: the compact output is a wire format, so readability is an opt-in separator only.
SEPARATORS = ("", " ")


def format_duration(seconds: int, sep: str = "") -> str:
    """Return the compact form of `seconds`, e.g. 5400 -> '1h30m', 0 -> '0s'.

    `sep=" "` puts one space between units (90061 -> '1d 1h 1m 1s'); `sep` may only be "" or
    " ". Zero units are left out. Negative input raises ValueError.
    """
    if sep not in SEPARATORS:
        raise ValueError(f"sep must be one of {SEPARATORS}, not {sep!r}")
    if seconds < 0:
        raise ValueError("negative duration")
    if seconds == 0:
        return "0s"
    parts: list[str] = []
    remaining = seconds
    for unit, size in UNITS.items():
        count, remaining = divmod(remaining, size)
        if count:
            parts.append(f"{count}{unit}")
    return sep.join(parts)
