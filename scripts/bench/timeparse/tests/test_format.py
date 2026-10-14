"""format_duration round-trips with parse_duration."""

import pytest
from timeparse import format_duration, parse_duration


@pytest.mark.parametrize(
    ("seconds", "text"), [(0, "0s"), (45, "45s"), (5400, "1h30m"), (90061, "1d1h1m1s")]
)
def test_format(seconds: int, text: str) -> None:
    assert format_duration(seconds) == text


def test_round_trip() -> None:
    for seconds in (1, 59, 61, 3599, 3601, 86399, 86401):
        assert parse_duration(format_duration(seconds)) == seconds


def test_negative() -> None:
    with pytest.raises(ValueError):
        format_duration(-1)
