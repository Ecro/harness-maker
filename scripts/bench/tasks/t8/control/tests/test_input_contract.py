"""The parse_duration input contract, one test per input class."""

import pytest
from timeparse import parse_duration


def test_ascii_whitespace_is_ignored() -> None:
    assert parse_duration(" 1h\t") == 3600
    assert parse_duration("\n45s\n") == 45


@pytest.mark.parametrize("text", [" 1h", "1h ", "+1h", "-1h", "1h-30m", "١h", "１h", "", " \t\n"])
def test_rejected_inputs(text: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(text)


def test_leading_zeros_and_the_largest_total() -> None:
    assert parse_duration("007s") == 7
    assert parse_duration("9223372036854775807s") == 2**63 - 1
    for text in ("9223372036854775808s", "106751991167301d", "106751991167300d16h"):
        with pytest.raises(ValueError):
            parse_duration(text)
