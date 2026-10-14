"""Hidden tests for t3: parse_iso_duration."""

import pytest
import timeparse
from timeparse.parse import parse_duration, parse_iso_duration


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("P1D", 86400),
        ("PT1H30M", 5400),
        ("P1DT2H", 93600),
        ("PT0S", 0),
        ("PT90M", 5400),
        ("PT45S", 45),
        ("P2DT3H4M5S", 2 * 86400 + 3 * 3600 + 4 * 60 + 5),
        ("PT1H5S", 3605),
        ("P0D", 0),
        ("  PT1M  ", 60),
        ("PT100000S", 100000),
    ],
)
def test_valid(text: str, seconds: int) -> None:
    assert parse_iso_duration(text) == seconds


@pytest.mark.parametrize(
    "text",
    [
        "P",
        "PT",
        "P1DT",
        "P1H",
        "PT1M1H",
        "PT1S1M",
        "PT1H2H",
        "pt1h",
        "P1d",
        "P1Y",
        "P1M",
        "P1W",
        "PT1.5S",
        "PT-1S",
        "-PT1S",
        "1H",
        "",
        "P1DT1H junk",
        "PT1H30",
    ],
)
def test_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_iso_duration(text)


def test_exported() -> None:
    assert timeparse.parse_iso_duration("PT1M") == 60


def test_parse_duration_unchanged() -> None:
    assert parse_duration("1h30m") == 5400
    with pytest.raises(ValueError):
        parse_duration("PT1H")
