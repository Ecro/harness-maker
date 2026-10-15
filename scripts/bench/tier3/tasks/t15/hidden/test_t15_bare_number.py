"""Hidden tests for t15: a bare number, in the unit the package already gives it (D-2)."""

import pytest
from timeparse import config, parse_duration


def test_a_bare_number_is_minutes() -> None:
    """A duration written as a bare number, with no unit at all, means that many minutes
    wherever timeparse accepts one.

    Source: docs/DECISIONS.md
    """
    assert parse_duration("90") == 5400
    assert parse_duration(" 90 ") == 5400
    assert parse_duration("1") == 60
    assert parse_duration("0") == 0


def test_durations_with_units_are_unchanged() -> None:
    """timeparse knows four units: `d` (86400 seconds), `h` (3600), `m` (60) and `s` (1).

    Source: docs/DECISIONS.md
    """
    assert parse_duration("90s") == 90
    assert parse_duration("90m") == 5400
    assert parse_duration("1h30m") == 5400
    assert parse_duration("2d") == 172800


def test_a_number_after_units_is_still_an_error() -> None:
    """A number without a unit after other units, as in `1h30`, is never accepted.

    Source: docs/DECISIONS.md
    """
    for text in ("1h30", "1h 30", "30m90", "1d1h1m1s5"):
        with pytest.raises(ValueError):
            parse_duration(text)


def test_config_load_is_unchanged() -> None:
    """A duration is anything `parse_duration` accepts, plus a bare number, which is minutes
    (D-2): `idle = 45` is 45 minutes.

    Source: docs/config.md
    """
    assert config.load("idle = 45\nread = 2m\nconnect = 30s\n") == {
        "idle": 2700, "read": 120, "connect": 30,
    }  # fmt: skip
