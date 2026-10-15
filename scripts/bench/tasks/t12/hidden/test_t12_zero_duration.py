"""Hidden tests for t12: a zero duration is rejected, every other documented behaviour kept."""

import pytest
from timeparse import format_duration, parse_duration


@pytest.mark.parametrize("text", ["0s", "0h0m", " 0D "])
def test_a_zero_duration_raises(text: str) -> None:
    """`parse_duration` raises `ValueError` when the total is zero: `parse_duration("0s")`,
    `parse_duration("0h0m")` and `parse_duration(" 0D ")` all raise."""
    with pytest.raises(ValueError):
        parse_duration(text)


def test_a_zero_unit_inside_a_nonzero_duration_is_accepted() -> None:
    """A zero unit inside a non-zero duration is still accepted: `parse_duration("0h1m")`
    returns 60 and `parse_duration("1h0m")` returns 3600."""
    assert parse_duration("0h1m") == 60
    assert parse_duration("1h0m") == 3600


def test_other_functions_keep_their_documented_behaviour() -> None:
    """Apart from `parse_duration` rejecting a zero duration, every other function in the
    package must behave as before."""
    from timeparse.schedule import normalize, total

    assert normalize("90m") == "1h30m"
    assert normalize(" 2H ") == "2h"
    assert normalize("0m") == "0s"
    assert total(["1h", "30m"]) == "1h30m"
    assert total([]) == "0s"
    assert format_duration(5400) == "1h30m"
    assert format_duration(0) == "0s"
