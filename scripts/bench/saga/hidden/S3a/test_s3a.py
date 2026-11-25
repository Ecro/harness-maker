"""S3a colour output (runs at the same time as S3b)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from remind import api
from remind.cli import main


def _seed() -> None:
    api.add("Overdue", datetime(2020, 1, 1, 9, 0, tzinfo=UTC))
    api.add("Future", datetime(2099, 1, 1, 9, 0, tzinfo=UTC))


def test_color_marks_overdue_red(save_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed()
    assert main(["list", "--color"]) == 0
    lines = capsys.readouterr().out.splitlines()
    overdue = next(line for line in lines if "Overdue" in line)
    future = next(line for line in lines if "Future" in line)
    assert "\x1b[31m" in overdue
    assert "\x1b[0m" in overdue
    assert "\x1b[" not in future


def test_no_color_by_default(save_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed()
    assert main(["list"]) == 0
    assert "\x1b[" not in capsys.readouterr().out


def test_no_color_flag(save_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed()
    assert main(["list", "--no-color"]) == 0
    assert "\x1b[" not in capsys.readouterr().out
