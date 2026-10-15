"""Weeks: formatting, parsing and the round trip."""

import pytest
from timeparse import format_duration, parse_duration


@pytest.mark.parametrize(
    ("seconds", "text"), [(604800, "1w"), (1209600, "2w"), (694861, "1w1d1h1m1s"),
                          (604799, "6d23h59m59s")],
)
def test_format_with_weeks(seconds: int, text: str) -> None:
    assert format_duration(seconds) == text


@pytest.mark.parametrize(("text", "seconds"), [("1w", 604800), ("2w3d", 1468800), ("1W", 604800)])
def test_parse_weeks(text: str, seconds: int) -> None:
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["1d1w", "1w1w"])
def test_weeks_must_come_first(text: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(text)


def test_round_trip_around_a_week() -> None:
    for seconds in range(604700, 604900):
        assert parse_duration(format_duration(seconds)) == seconds
