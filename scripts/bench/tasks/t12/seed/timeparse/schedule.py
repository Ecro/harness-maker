"""Normalise and add durations written by people."""

from __future__ import annotations

from timeparse.format import format_duration
from timeparse.parse import parse_duration


def normalize(text: str) -> str:
    """Return the canonical form of a duration string.

    normalize("90m") -> "1h30m", normalize(" 2H ") -> "2h", normalize("0m") -> "0s".
    """
    return format_duration(parse_duration(text))


def total(texts: list[str]) -> str:
    """Return the sum of several durations in canonical form.

    total(["1h", "30m"]) -> "1h30m", total([]) -> "0s".
    """
    return format_duration(sum(parse_duration(text) for text in texts))
