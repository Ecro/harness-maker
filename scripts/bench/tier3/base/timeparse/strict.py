"""Strict durations for the scheduler's API: the canonical form only.

A strict duration is lower case, has no surrounding whitespace, no zero unit and no leading
zero, and lists its units largest first.
"""

from __future__ import annotations

from timeparse.parse import _TOKEN, _rank, parse_duration


def is_canonical(text: str) -> bool:
    """is_canonical("1h30m") -> True; "1h0m", " 1h", "1H", "01h" and "" -> False."""
    tokens = list(_TOKEN.finditer(text))
    if not tokens or "".join(t.group(0) for t in tokens) != text:
        return False
    ranks = []
    for token in tokens:
        amount, unit = token.groups()
        if amount.startswith("0"):
            return False
        try:
            ranks.append(_rank(unit))
        except ValueError:
            return False
    return ranks == sorted(set(ranks))


def parse_strict(text: str) -> int:
    """Return the seconds in a canonical duration: parse_strict("1h30m") -> 5400.

    Anything that is_canonical rejects raises ValueError.
    """
    if not is_canonical(text):
        raise ValueError(f"not a canonical duration: {text!r}")
    return parse_duration(text)
