"""Regression tests for the trailing-text bug: text after the last unit is rejected."""

import pytest
from timeparse import parse_duration


@pytest.mark.parametrize("text", ["1h30m5", "1h30m!", "2d junk", "45sx"])
def test_trailing_text_raises(text: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize(
    ("text", "seconds"), [(" 1h30m ", 5400), ("1H30M", 5400), ("0s", 0), ("100000s", 100000)]
)
def test_documented_behaviour_is_kept(text: str, seconds: int) -> None:
    assert parse_duration(text) == seconds
