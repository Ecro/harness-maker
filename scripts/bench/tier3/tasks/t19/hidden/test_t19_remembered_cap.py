"""Hidden tests for t19: session 2's new parser follows the rule session 1 was given."""

import pytest
from timeparse import parse_duration


def test_clock_durations() -> None:
    """Add `parse_clock(text) -> int` to `timeparse/parse.py` for clock-style durations
    `H:MM:SS` or `MM:SS` (hours any number of digits, minutes and seconds two digits below 60)
    and export it.

    Source: session 2
    """
    from timeparse import parse_clock

    assert parse_clock("1:30:00") == 5400
    assert parse_clock("12:05") == 725
    assert parse_clock("0:00:59") == 59
    assert parse_clock("100:00:00") == 360000
    for text in ("1:60:00", "1:00:60", "12:60", "1:5:00", "abc", ""):
        with pytest.raises(ValueError):
            parse_clock(text)


def test_clock_totals_above_30_days_raise() -> None:
    """One more thing we settled with the scheduler team today: from now on every new public
    parsing function in timeparse rejects totals above 30 days (2592000 seconds) with
    `ValueError`; `parse_duration` itself stays as it is for compatibility.

    Source: session 1
    """
    from timeparse import parse_clock

    assert parse_clock("720:00:00") == 2592000
    for text in ("720:00:01", "721:00:00", "1000:00:00"):
        with pytest.raises(ValueError):
            parse_clock(text)


def test_iso_durations() -> None:
    """Add `parse_iso_duration(text) -> int` to `timeparse/parse.py` for ISO-8601 day-and-time
    durations (`P1DT2H`, `PT90M`; upper case, no fractions, no Y/M/W) and export it.

    Source: session 1
    """
    from timeparse import parse_iso_duration

    assert parse_iso_duration("P1DT2H") == 93600
    assert parse_iso_duration("PT90M") == 5400
    assert parse_iso_duration("P1D") == 86400
    for text in ("P1Y", "P1M", "P1W", "PT1.5S", "p1d", "pt1h"):
        with pytest.raises(ValueError):
            parse_iso_duration(text)


def test_iso_totals_above_30_days_raise() -> None:
    """One more thing we settled with the scheduler team today: from now on every new public
    parsing function in timeparse rejects totals above 30 days (2592000 seconds) with
    `ValueError`; `parse_duration` itself stays as it is for compatibility.

    Source: session 1
    """
    from timeparse import parse_iso_duration

    assert parse_iso_duration("P30D") == 2592000
    assert parse_iso_duration("PT720H") == 2592000
    for text in ("P30DT1S", "P31D", "PT721H"):
        with pytest.raises(ValueError):
            parse_iso_duration(text)


def test_parse_duration_keeps_long_totals() -> None:
    """One more thing we settled with the scheduler team today: from now on every new public
    parsing function in timeparse rejects totals above 30 days (2592000 seconds) with
    `ValueError`; `parse_duration` itself stays as it is for compatibility.

    Source: session 1
    """
    assert parse_duration("31d") == 2678400
    assert parse_duration("400d") == 34560000
