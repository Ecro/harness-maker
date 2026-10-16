"""Read and write timeout config files: one `name = duration` line per timeout.

A value without a unit is minutes, as in the cron-era files this format replaced (D-2).
Blank lines and `#` comments are ignored. See docs/config.md for the format and its errors.
"""

from __future__ import annotations

import re

from timeparse.format import format_duration
from timeparse.parse import parse_duration

_NAME = re.compile(r"[a-z][a-z0-9_]*")


class ConfigError(ValueError):
    """A config line that cannot be read; the message names the line."""


def _bad_duration(number: int, exc: ValueError) -> str:
    match = re.search(r"invalid duration: '(.*)'", str(exc))
    if match is None:
        return f"config line {number}: bad duration"
    return f"config line {number}: bad duration '{match.group(1)}'"


def load(text: str) -> dict[str, int]:
    """Return {name: seconds} for each `name = duration` line of `text`.

    load("connect = 30s\\nread = 2\\n") -> {"connect": 30, "read": 120}.
    """
    values: dict[str, int] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.partition("#")[0].strip()
        if not line:
            continue
        name, sep, value = (part.strip() for part in line.partition("="))
        if not sep or not _NAME.fullmatch(name):
            raise ConfigError(f"config line {number}: expected 'name = duration'")
        if name in values:
            raise ConfigError(f"config line {number}: {name} is set twice")
        if value.isdigit():
            value += "m"  # D-2: a bare number is minutes
        try:
            values[name] = parse_duration(value)
        except ValueError as exc:
            raise ConfigError(_bad_duration(number, exc)) from None
    return values


def save(values: dict[str, int]) -> str:
    """Return config text for `values`, one line per name in sorted order.

    save({"read": 120, "connect": 30}) -> "connect = 30s\\nread = 2m\\n".
    """
    return "".join(f"{name} = {format_duration(values[name])}\n" for name in sorted(values))
