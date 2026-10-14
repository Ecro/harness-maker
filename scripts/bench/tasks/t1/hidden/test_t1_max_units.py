"""Hidden tests for t1: format_duration(max_units)."""

import pytest
from timeparse import parse_duration
from timeparse.format import format_duration


@pytest.mark.parametrize(
    ("seconds", "max_units", "expected"),
    [
        (5430, 1, "2h"),
        (5399, 2, "1h30m"),
        (3601, 2, "1h"),
        (86399, 2, "1d"),
        (90, 1, "2m"),
        (89, 1, "1m"),
        (0, 1, "0s"),
        (45, 1, "45s"),
        (59, 3, "59s"),
        (3599, 1, "1h"),
        (5400, 1, "2h"),
        (5399, 1, "1h"),
        (90061, 2, "1d1h"),
        (90061, 3, "1d1h1m"),
        (172799, 2, "2d"),
        (86430, 3, "1d1m"),
    ],
)
def test_max_units(seconds: int, max_units: int, expected: str) -> None:
    assert format_duration(seconds, max_units=max_units) == expected


@pytest.mark.parametrize("seconds", [0, 1, 61, 3601, 90061, 172799])
def test_none_and_wide_windows_keep_todays_output(seconds: int) -> None:
    today = format_duration(seconds)
    assert format_duration(seconds, max_units=None) == today
    assert format_duration(seconds, max_units=4) == today
    assert format_duration(seconds, max_units=9) == today


@pytest.mark.parametrize("max_units", [0, -1])
def test_rejects_small_max_units(max_units: int) -> None:
    with pytest.raises(ValueError):
        format_duration(100, max_units=max_units)


def test_negative_still_rejected() -> None:
    with pytest.raises(ValueError):
        format_duration(-5, max_units=1)


def test_output_parses_back() -> None:
    for seconds in range(0, 200000, 997):
        for max_units in (1, 2, 3):
            text = format_duration(seconds, max_units=max_units)
            assert abs(parse_duration(text) - seconds) <= max(seconds, 1)
