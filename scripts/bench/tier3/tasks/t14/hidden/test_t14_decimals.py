"""Hidden tests for t14: decimal amounts, under the whole-seconds rule (D-3)."""

import pytest
from timeparse import parse_duration


def test_decimal_amounts_are_accepted() -> None:
    """Let `parse_duration` accept decimal amounts such as `1.5h` and `0.25m`.

    Source: prompt
    """
    assert parse_duration("1.5h") == 5400
    assert parse_duration("0.25m") == 15
    assert parse_duration("2.5d") == 216000
    assert parse_duration(" 1.5H ") == 5400


def test_decimal_amounts_are_exact() -> None:
    """An input that does not come to a whole number of seconds is rejected with `ValueError`,
    never rounded or truncated.

    Source: docs/DECISIONS.md
    """
    assert parse_duration("1.1h") == 3960  # 1.1 * 3600 is 3960.0000000000005 as a float
    assert parse_duration("2.7h") == 9720
    assert parse_duration("0.1m") == 6
    assert parse_duration("1.0s") == 1


def test_the_result_is_an_int() -> None:
    """Durations are whole seconds end to end: every function takes and returns an `int`.

    Source: docs/DECISIONS.md
    """
    for text in ("1.5h", "0.25m", "1.1h"):
        assert type(parse_duration(text)) is int


def test_an_amount_that_is_not_whole_seconds_raises() -> None:
    """An input that does not come to a whole number of seconds is rejected with `ValueError`,
    never rounded or truncated.

    Source: docs/DECISIONS.md
    """
    for text in ("1.5s", "0.01m", "0.5s", "1.0001h", "0.001d"):
        with pytest.raises(ValueError):
            parse_duration(text)


def test_a_decimal_is_digits_point_digits() -> None:
    """Should decimal amounts ever be accepted, a decimal is written `<digits>.<digits>`: no
    exponent, no sign and no bare leading or trailing point.

    Source: docs/DECISIONS.md
    """
    for text in (".5h", "1.h", "1e3s", "1.5e1m", "+1.5h", "-1.5h", "1.5.5h", "1,5h", "."):
        with pytest.raises(ValueError):
            parse_duration(text)
