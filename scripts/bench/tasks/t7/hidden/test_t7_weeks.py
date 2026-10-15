"""Hidden tests for t7: a week unit, with the round-trip invariant kept."""

import pytest
from timeparse import format_duration, parse_duration


def test_format_uses_weeks() -> None:
    """`format_duration` uses weeks as its largest unit: `format_duration(604800)` returns
    `"1w"`, `format_duration(1209600)` returns `"2w"` and `format_duration(694861)` returns
    `"1w1d1h1m1s"`."""
    assert format_duration(604800) == "1w"
    assert format_duration(1209600) == "2w"
    assert format_duration(694861) == "1w1d1h1m1s"


def test_values_below_a_week_are_unchanged() -> None:
    """Values below one week are formatted exactly as today: `format_duration(604799)` returns
    `"6d23h59m59s"`."""
    assert format_duration(604799) == "6d23h59m59s"


def test_parse_accepts_weeks() -> None:
    """`parse_duration` accepts `w` with the same rules as the other units:
    `parse_duration("1w")` returns 604800, `parse_duration("2w3d")` returns 1468800 and
    `parse_duration("1W")` returns 604800."""
    assert parse_duration("1w") == 604800
    assert parse_duration("2w3d") == 1468800
    assert parse_duration("1W") == 604800


@pytest.mark.parametrize("text", ["1d1w", "1w1w"])
def test_w_comes_before_d(text: str) -> None:
    """`w` comes before `d` in the unit order, so `"1d1w"` and `"1w1w"` raise `ValueError`."""
    with pytest.raises(ValueError):
        parse_duration(text)


_EDGES = [0, 1, 59, 60, 3599, 3600, 86399, 86400, 604799, 604800, 604801, 1209600, 10000000]


def test_round_trip_invariant_holds() -> None:
    """The round-trip invariant must keep holding: for every integer `s` from 0 to 10000000,
    `parse_duration(format_duration(s)) == s`."""
    for seconds in [*_EDGES, *range(0, 10000001, 7919)]:
        assert parse_duration(format_duration(seconds)) == seconds
