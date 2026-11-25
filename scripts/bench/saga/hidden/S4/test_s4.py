"""S4 time zone setting (S4 is interrupted, S4' finishes it)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from remind import api
from remind.cli import main
from remind.fmt import format_due


def _tz(directory: Path, name: str) -> None:
    (directory / "remind.cfg").write_text(f"[remind]\ntz = {name}\n")


def test_parse_when_uses_tz(save_file: Path, tmp_path: Path) -> None:
    _tz(tmp_path, "Asia/Seoul")
    assert api.parse_when("2026-01-05 09:00") == datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def test_format_due_uses_tz(save_file: Path, tmp_path: Path) -> None:
    _tz(tmp_path, "Asia/Seoul")
    assert format_due(datetime(2026, 1, 5, 0, 0, tzinfo=UTC)) == "2026-01-05 09:00"


def test_list_uses_tz(save_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _tz(tmp_path, "America/New_York")
    api.add("x", datetime(2026, 1, 5, 14, 0, tzinfo=UTC))
    assert main(["list"]) == 0
    assert "2026-01-05 09:00" in capsys.readouterr().out


def test_unset_tz_keeps_current_behaviour(save_file: Path) -> None:
    assert api.parse_when("2026-01-05 09:00") == datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
    assert format_due(datetime(2026, 1, 5, 9, 0, tzinfo=UTC)) == "2026-01-05 09:00"


def test_unknown_zone_exits_2(
    save_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api.add("x", datetime(2026, 1, 5, 14, 0, tzinfo=UTC))
    _tz(tmp_path, "Mars/Olympus")
    assert main(["list"]) == 2
