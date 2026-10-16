"""Hidden tests for t13: issue #21 is fixed the way its ruling (D-6) says."""

import pytest
from timeparse import config, format_duration, parse_duration
from timeparse.schedule import normalize

# format_duration exactly as the start tree has it, the oracle for the compact output.
_UNITS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def _compact(seconds: int) -> str:
    if seconds == 0:
        return "0s"
    parts = []
    for unit, size in _UNITS.items():
        count, seconds = divmod(seconds, size)
        if count:
            parts.append(f"{count}{unit}")
    return "".join(parts)


_SWEEP = sorted({*range(0, 10_000_000, 7919), 1, 59, 60, 61, 3599, 3600, 3601, 86399, 86400,
                 86401, 90061, 604799, 604800, 604801, 1209600, 10_000_000})  # fmt: skip


def test_a_space_separator_is_opt_in() -> None:
    """Readability comes from an opt-in separator instead: `format_duration(seconds, sep=" ")`
    puts one space between units, so `format_duration(90061, sep=" ")` returns
    `"1d 1h 1m 1s"`.

    Source: docs/DECISIONS.md
    """
    assert format_duration(90061, sep=" ") == "1d 1h 1m 1s"
    assert format_duration(5400, sep=" ") == "1h 30m"
    assert format_duration(45, sep=" ") == "45s"


def test_any_other_separator_raises() -> None:
    """`sep` may only be `""` (the default) or `" "`; any other value raises `ValueError`.

    Source: docs/DECISIONS.md
    """
    assert format_duration(90061, sep="") == "1d1h1m1s"
    for sep in ("-", "_", ", ", "  ", "\t"):
        with pytest.raises(ValueError):
            format_duration(90061, sep=sep)


def test_compact_output_is_unchanged() -> None:
    """The compact output of `format_duration` (`1d1h1m1s`, `0s`) is a stable wire format: the
    scheduler stores `schedule.normalize` results and `config.save` writes it into config files
    that other tools read back, so the default output stays exactly as it is.

    Source: docs/DECISIONS.md
    """
    for seconds in _SWEEP:
        assert format_duration(seconds) == _compact(seconds), seconds


def test_normalize_and_config_round_trips_hold() -> None:
    """The compact output of `format_duration` (`1d1h1m1s`, `0s`) is a stable wire format: the
    scheduler stores `schedule.normalize` results and `config.save` writes it into config files
    that other tools read back, so the default output stays exactly as it is.

    Source: docs/DECISIONS.md
    """
    assert normalize("25h1m1s") == "1d1h1m1s"
    assert normalize("90m") == "1h30m"
    values = {"connect": 30, "read": 90061, "idle": 2700}
    text = config.save(values)
    assert text == "connect = 30s\nidle = 45m\nread = 1d1h1m1s\n"
    assert config.load(text) == values
    for seconds in (90061, 5400, 0):
        assert parse_duration(normalize(f"{seconds}s")) == seconds
