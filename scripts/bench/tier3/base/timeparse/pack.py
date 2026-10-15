"""Pack durations into short strings for storage, and back.

A packed string lists each non-zero unit as `<index>:<count>`, comma-separated, where the
index is the unit's position in UNITS. Packed strings are stored in user databases; the format
is frozen.
"""

from __future__ import annotations

from timeparse.parse import UNITS


def pack(seconds: int) -> str:
    """Return the packed form of `seconds`.

    pack(3600) -> "1:1", pack(90061) -> "0:1,1:1,2:1,3:1", pack(0) -> "".
    """
    if seconds < 0:
        raise ValueError("negative duration")
    order = list(UNITS)
    parts: list[str] = []
    remaining = seconds
    for unit in order:
        count, remaining = divmod(remaining, UNITS[unit])
        if count:
            parts.append(f"{order.index(unit)}:{count}")
    return ",".join(parts)


def unpack(text: str) -> int:
    """Return the seconds in a packed string: unpack("1:1") -> 3600, unpack("") -> 0."""
    order = list(UNITS)
    total = 0
    for part in filter(None, text.split(",")):
        index, sep, count = part.partition(":")
        if not sep or not index.isdigit() or not count.isdigit() or int(index) >= len(order):
            raise ValueError(f"invalid packed duration: {text!r}")
        total += int(count) * UNITS[order[int(index)]]
    return total
