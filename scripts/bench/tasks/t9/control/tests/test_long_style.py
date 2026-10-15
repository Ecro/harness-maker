"""The long output style and its unit names."""

import pytest
from timeparse import format_duration


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(5400, "1 hour, 30 minutes"), (90061, "1 day, 1 hour, 1 minute, 1 second"), (0, "0 seconds")],
)
def test_long_style(seconds: int, text: str) -> None:
    assert format_duration(seconds, style="long") == text


def test_compact_is_the_default() -> None:
    assert format_duration(5400) == format_duration(5400, style="compact") == "1h30m"


@pytest.mark.parametrize("style", ["short", ""])
def test_unknown_style_raises(style: str) -> None:
    with pytest.raises(ValueError):
        format_duration(60, style=style)


@pytest.mark.parametrize("style", ["compact", "long"])
def test_negative_seconds_raise(style: str) -> None:
    with pytest.raises(ValueError):
        format_duration(-1, style=style)
