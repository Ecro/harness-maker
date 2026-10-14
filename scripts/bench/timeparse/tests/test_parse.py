"""parse_duration on the documented grammar."""

import pytest
from timeparse import parse_duration


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("45s", 45), ("1h30m", 5400), ("2d", 172800), (" 1M ", 60), ("1d1h1m1s", 90061)],
)
def test_valid(text: str, seconds: int) -> None:
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["", "10", "1x", "30m1h", "1h1h", "1h 30m", "h"])
def test_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(text)
