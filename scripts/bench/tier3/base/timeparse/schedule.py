"""Normalise and add durations written by people, for the scheduler."""

from __future__ import annotations

from timeparse.format import format_duration
from timeparse.parse import parse_duration


def normalize(text: str) -> str:
    """Return the canonical form of a duration string.

    normalize("90m") -> "1h30m", normalize(" 2H ") -> "2h", normalize("0m") -> "0s".
    The scheduler stores this form, so it must parse back to the same number of seconds.
    """
    return format_duration(parse_duration(text))


def total(texts: list[str]) -> str:
    """Return the sum of several durations in canonical form.

    total(["1h", "30m"]) -> "1h30m", total([]) -> "0s".
    """
    return format_duration(sum(parse_duration(text) for text in texts))


def split(text: str, parts: int) -> list[str]:
    """Split a duration into `parts` near-equal slices, largest first, in canonical form.

    split("1h", 4) -> ["15m", "15m", "15m", "15m"], split("10s", 3) -> ["4s", "3s", "3s"].
    """
    if parts < 1:
        raise ValueError("parts must be at least 1")
    size, extra = divmod(parse_duration(text), parts)
    return [format_duration(size + (1 if i < extra else 0)) for i in range(parts)]
