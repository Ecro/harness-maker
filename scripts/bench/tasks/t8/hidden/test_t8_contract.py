"""Hidden tests for t8: the stated input contract of parse_duration, one test per class."""

import pytest
from timeparse import parse_duration


def test_surrounding_ascii_whitespace_is_ignored() -> None:
    r"""Surrounding spaces, tabs and newlines are ignored: `parse_duration(" 1h\t")` returns
    3600 and `parse_duration("\n45s\n")` returns 45."""
    assert parse_duration(" 1h\t") == 3600
    assert parse_duration("\n45s\n") == 45


@pytest.mark.parametrize("text", ["\u00a01h", "1h\u2003"])
def test_other_whitespace_raises(text: str) -> None:
    r"""Any other whitespace raises `ValueError`, also around the text: `"\u00a01h"` (a
    no-break space) and `"1h\u2003"` (an em space) raise `ValueError`."""
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["+1h", "-1h", "1h-30m"])
def test_a_sign_raises(text: str) -> None:
    """A sign raises `ValueError`: `"+1h"`, `"-1h"` and `"1h-30m"` raise `ValueError`."""
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["\u0661h", "\uff11h"])
def test_only_ascii_digits_are_digits(text: str) -> None:
    r"""Only the ASCII digits 0 to 9 are digits: `"\u0661h"` (an Arabic-Indic one) and
    `"\uff11h"` (a fullwidth one) raise `ValueError`."""
    with pytest.raises(ValueError):
        parse_duration(text)


def test_leading_zeros_are_allowed() -> None:
    """Leading zeros are allowed: `parse_duration("007s")` returns 7."""
    assert parse_duration("007s") == 7


def test_the_largest_total_is_accepted() -> None:
    """The largest accepted total is 9223372036854775807 seconds (2**63 - 1):
    `parse_duration("9223372036854775807s")` returns 9223372036854775807, while
    `"9223372036854775808s"`, `"106751991167301d"` and `"106751991167300d16h"` raise
    `ValueError`."""
    assert parse_duration("9223372036854775807s") == 9223372036854775807


@pytest.mark.parametrize(
    "text", ["9223372036854775808s", "106751991167301d", "106751991167300d16h"]
)
def test_a_larger_total_raises(text: str) -> None:
    """The largest accepted total is 9223372036854775807 seconds (2**63 - 1):
    `parse_duration("9223372036854775807s")` returns 9223372036854775807, while
    `"9223372036854775808s"`, `"106751991167301d"` and `"106751991167300d16h"` raise
    `ValueError`."""
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["", " \t\n"])
def test_empty_or_blank_raises(text: str) -> None:
    r"""An empty or all-whitespace string raises `ValueError`: `""` and `" \t\n"`."""
    with pytest.raises(ValueError):
        parse_duration(text)
