"""Hidden tests for t16: weeks, while the frozen packed format keeps its meaning."""

import pytest
from timeparse import config, format_duration, parse_duration
from timeparse.pack import pack, unpack
from timeparse.schedule import normalize, split
from timeparse.strict import parse_strict

# pack() of the unchanged start tree, recorded before any arm ran (a differential oracle).
_PACKED = {
    0: "", 1: "3:1", 59: "3:59", 60: "2:1", 61: "2:1,3:1", 3599: "2:59,3:59", 3600: "1:1",
    3601: "1:1,3:1", 5400: "1:1,2:30", 46411: "1:12,2:53,3:31", 86399: "1:23,2:59,3:59",
    86400: "0:1", 86401: "0:1,3:1", 90061: "0:1,1:1,2:1,3:1", 92822: "0:1,1:1,2:47,3:2",
    139233: "0:1,1:14,2:40,3:33", 172800: "0:2", 185644: "0:2,1:3,2:34,3:4",
    232055: "0:2,1:16,2:27,3:35", 278466: "0:3,1:5,2:21,3:6", 324877: "0:3,1:18,2:14,3:37",
    371288: "0:4,1:7,2:8,3:8", 417699: "0:4,1:20,2:1,3:39", 464110: "0:5,1:8,2:55,3:10",
    510521: "0:5,1:21,2:48,3:41", 518400: "0:6", 556932: "0:6,1:10,2:42,3:12",
    603343: "0:6,1:23,2:35,3:43", 604799: "0:6,1:23,2:59,3:59",
}  # fmt: skip


def test_parse_duration_takes_weeks_first() -> None:
    """Add weeks (`w`, 604800 seconds) as the largest unit of `parse_duration` and
    `format_duration`.

    Source: prompt
    """
    assert parse_duration("1w") == 604800
    assert parse_duration("2w3d") == 1468800
    assert parse_duration("1W") == 604800
    assert parse_duration("1w1d1h1m1s") == 694861
    for text in ("1d1w", "1w1w", "1h1w"):
        with pytest.raises(ValueError):
            parse_duration(text)


def test_format_duration_writes_weeks() -> None:
    """Add weeks (`w`, 604800 seconds) as the largest unit of `parse_duration` and
    `format_duration`.

    Source: prompt
    """
    assert format_duration(604800) == "1w"
    assert format_duration(1209600) == "2w"
    assert format_duration(694861) == "1w1d1h1m1s"
    assert format_duration(604799) == "6d23h59m59s"
    for seconds in (604800, 694861, 1468800, 10_000_000):
        assert parse_duration(format_duration(seconds)) == seconds


def test_pack_is_unchanged_below_a_week() -> None:
    """Every other function in the package keeps its current behaviour for durations below one
    week.

    Source: prompt
    """
    for seconds, packed in _PACKED.items():
        assert pack(seconds) == packed, seconds


def test_stored_packed_strings_still_decode() -> None:
    """Packed strings are stored in user databases; the format is frozen.

    Source: timeparse/pack.py
    """
    for seconds, packed in _PACKED.items():
        assert unpack(packed) == seconds, packed
    assert unpack("0:1") == 86400
    assert unpack("1:2,2:30") == 9000


def test_other_functions_are_unchanged_below_a_week() -> None:
    """Every other function in the package keeps its current behaviour for durations below one
    week.

    Source: prompt
    """
    assert normalize("90m") == "1h30m"
    assert normalize("143h") == "5d23h"
    assert split("1h", 4) == ["15m", "15m", "15m", "15m"]
    assert config.save({"read": 90061}) == "read = 1d1h1m1s\n"
    assert config.load("read = 6d23h\n") == {"read": 601200}
    assert parse_strict("6d23h59m59s") == 604799
