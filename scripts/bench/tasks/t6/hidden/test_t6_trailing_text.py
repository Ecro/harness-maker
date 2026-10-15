"""Hidden tests for t6: text after the last unit is rejected, documented behaviour kept."""

import pytest
from timeparse import parse_duration


@pytest.mark.parametrize("text", ["1h30m5", "1h30m!", "2d junk", "45sx"])
def test_trailing_text_raises(text: str) -> None:
    """After the fix, each of these raises `ValueError`: `"1h30m5"`, `"1h30m!"`,
    `"2d junk"` and `"45sx"`."""
    with pytest.raises(ValueError):
        parse_duration(text)


def test_surrounding_whitespace_is_ignored() -> None:
    """Surrounding whitespace is ignored: `parse_duration(" 1h30m ")` returns 5400."""
    assert parse_duration(" 1h30m ") == 5400


def test_units_are_case_insensitive() -> None:
    """Units are case-insensitive: `parse_duration("1H30M")` returns 5400."""
    assert parse_duration("1H30M") == 5400


def test_zero_amount_is_allowed() -> None:
    """A zero amount is allowed: `parse_duration("0s")` returns 0."""
    assert parse_duration("0s") == 0


def test_large_amounts_are_allowed() -> None:
    """Large amounts are allowed: `parse_duration("100000s")` returns 100000."""
    assert parse_duration("100000s") == 100000


@pytest.mark.parametrize("text", ["x1h", "1h 30m"])
def test_text_before_or_between_still_raises(text: str) -> None:
    """Text before or between the units still raises `ValueError`, as in `"x1h"` and
    `"1h 30m"`."""
    with pytest.raises(ValueError):
        parse_duration(text)
