from __future__ import annotations

from pathlib import Path

import pytest
from remind.cli import main


def test_add_then_list(save_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["add", "Call the bank", "--when", "2026-01-05 09:00"]) == 0
    ident = capsys.readouterr().out.strip()
    assert main(["list"]) == 0
    assert ident in capsys.readouterr().out


def test_bad_time_exits_2(save_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["add", "x", "--when", "tomorrow"]) == 2
    assert "remind:" in capsys.readouterr().err
