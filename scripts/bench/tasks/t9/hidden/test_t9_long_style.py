"""Hidden tests for t9: a long output style that follows the one unit table."""

from collections.abc import Iterator

import pytest
import timeparse.format as fmt
from timeparse import format_duration
from timeparse.parse import UNITS


@pytest.fixture
def units() -> Iterator[dict[str, int]]:
    """UNITS, restored after the test changes it in place."""
    saved = dict(UNITS)
    yield UNITS
    UNITS.clear()
    UNITS.update(saved)


def test_compact_is_the_default() -> None:
    """`style="compact"` is the default and gives exactly today's output."""
    for seconds, text in ((0, "0s"), (45, "45s"), (5400, "1h30m"), (90061, "1d1h1m1s")):
        assert format_duration(seconds) == text
        assert format_duration(seconds, style="compact") == text


def test_long_style_names_each_unit() -> None:
    """The name is singular for a count of 1 and plural otherwise: `format_duration(5400,
    style="long")` returns `"1 hour, 30 minutes"` and `format_duration(90061, style="long")`
    returns `"1 day, 1 hour, 1 minute, 1 second"`."""
    assert format_duration(5400, style="long") == "1 hour, 30 minutes"
    assert format_duration(90061, style="long") == "1 day, 1 hour, 1 minute, 1 second"


def test_long_zero() -> None:
    """Zero is `"0 seconds"` in the long style."""
    assert format_duration(0, style="long") == "0 seconds"


def test_other_styles_and_negative_seconds_raise() -> None:
    """Any other `style` raises `ValueError`, and negative seconds still raise `ValueError` in
    both styles."""
    with pytest.raises(ValueError):
        format_duration(5, style="short")
    for style in ("compact", "long"):
        with pytest.raises(ValueError):
            format_duration(-1, style=style)


def test_names_live_in_one_table() -> None:
    """The names live in one table, `UNIT_NAMES` in `timeparse/format.py`, which maps each unit
    letter to its singular and plural names, for example `"h": ("hour", "hours")`."""
    assert fmt.UNIT_NAMES["h"] == ("hour", "hours")


def test_adding_a_unit_changes_both_styles(
    units: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """For example, with `"w": 604800` added first to `UNITS` and `"w": ("week", "weeks")` added
    to `UNIT_NAMES`, `format_duration(694861)` returns `"1w1d1h1m1s"` and
    `format_duration(694861, style="long")` returns `"1 week, 1 day, 1 hour, 1 minute, 1
    second"`."""
    rest = dict(units)
    units.clear()
    units.update({"w": 604800, **rest})
    monkeypatch.setitem(fmt.UNIT_NAMES, "w", ("week", "weeks"))
    assert format_duration(694861) == "1w1d1h1m1s"
    assert format_duration(694861, style="long") == "1 week, 1 day, 1 hour, 1 minute, 1 second"


def test_removing_a_unit_changes_both_styles(units: dict[str, int]) -> None:
    """With `"d"` removed from `UNITS`, `format_duration(90061)` returns `"25h1m1s"` and
    `format_duration(90061, style="long")` returns `"25 hours, 1 minute, 1 second"`."""
    del units["d"]
    assert format_duration(90061) == "25h1m1s"
    assert format_duration(90061, style="long") == "25 hours, 1 minute, 1 second"
