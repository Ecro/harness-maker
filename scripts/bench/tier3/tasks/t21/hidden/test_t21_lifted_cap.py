"""Hidden tests for t21 (guard): session 2 lifts the limit session 1 was given."""

import pytest
from timeparse import parse_duration


def test_clock_durations_of_any_length() -> None:
    """Add `parse_clock(text) -> int` to `timeparse/parse.py` for clock-style durations
    `H:MM:SS` or `MM:SS` (hours any number of digits, minutes and seconds two digits below 60)
    and export it, and lift the limit from `parse_iso_duration`.

    Source: session 2
    """
    from timeparse import parse_clock

    assert parse_clock("1:30:00") == 5400
    assert parse_clock("12:05") == 725
    assert parse_clock("1000:00:00") == 3600000
    assert parse_clock("720:00:01") == 2592001
    for text in ("1:60:00", "1:00:60", "12:60", "1:5:00", "abc", ""):
        with pytest.raises(ValueError):
            parse_clock(text)


def test_iso_durations_without_the_limit() -> None:
    """The scheduler now holds any length, so the 30-day limit is gone.

    Source: session 2
    """
    from timeparse import parse_iso_duration

    assert parse_iso_duration("P40D") == 3456000
    assert parse_iso_duration("P30DT1S") == 2592001
    assert parse_iso_duration("P1DT2H") == 93600
    assert parse_iso_duration("PT90M") == 5400
    for text in ("P1Y", "P1W", "PT1.5S", "p1d"):
        with pytest.raises(ValueError):
            parse_iso_duration(text)


def test_parse_duration_keeps_long_totals() -> None:
    """One more thing we settled with the scheduler team today: from now on every new public
    parsing function in timeparse rejects totals above 30 days (2592000 seconds) with
    `ValueError`; `parse_duration` itself stays as it is for compatibility.

    Source: session 1
    """
    assert parse_duration("31d") == 2678400
