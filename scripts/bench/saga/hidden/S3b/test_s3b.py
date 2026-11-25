"""S3b rename --when to --due (runs at the same time as S3a)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from remind import api
from remind.cli import main


def test_due_option(save_file: Path) -> None:
    assert main(["add", "x", "--due", "2026-01-05 09:00"]) == 0
    [(due, text, _id)] = api.upcoming()
    assert (due, text) == (datetime(2026, 1, 5, 9, 0, tzinfo=UTC), "x")


def test_when_still_works(save_file: Path) -> None:
    assert main(["add", "y", "--when", "2026-01-05 09:00"]) == 0
    assert [text for _due, text, _id in api.upcoming()] == ["y"]


def test_help_shows_due_not_when(save_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["add", "--help"])
    out = capsys.readouterr().out
    assert "--due" in out
    assert "--when" not in out
