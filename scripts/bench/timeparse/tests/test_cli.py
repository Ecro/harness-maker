"""The CLI prints seconds and exits 2 on bad input."""

import pytest
from timeparse.cli import main


def test_prints_each(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["1h", "30s"]) == 0
    assert capsys.readouterr().out.split() == ["3600", "30"]


def test_invalid_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["1h", "nope"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "nope" in captured.err
