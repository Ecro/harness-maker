"""Hidden tests for t11: the CLI reports every invalid argument."""

import pytest
from timeparse.cli import main


def test_every_invalid_argument_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    """When one or more arguments are invalid, `main` prints one line `error: invalid duration:
    '<text>'` to stderr for each invalid argument, in argument order, prints nothing to stdout
    and returns 2: `main(["1h", "nope", "2x", "30s"])` prints the lines for `'nope'` and `'2x'`
    and returns 2."""
    assert main(["1h", "nope", "2x", "30s"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "error: invalid duration: 'nope'",
        "error: invalid duration: '2x'",
    ]


def test_total_reports_every_invalid_argument(capsys: pytest.CaptureFixture[str]) -> None:
    """The same holds with `--total`: `main(["--total", "1h", "nope", "2x"])` prints the two
    error lines, prints no total and returns 2."""
    assert main(["--total", "1h", "nope", "2x"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "error: invalid duration: 'nope'",
        "error: invalid duration: '2x'",
    ]


def test_valid_arguments_behave_as_today(capsys: pytest.CaptureFixture[str]) -> None:
    """Valid arguments behave as today: `main(["1h", "30s"])` prints `3600` and `30`, and
    `main(["--total", "1h", "30s"])` prints `3630`; both return 0."""
    assert main(["1h", "30s"]) == 0
    assert capsys.readouterr().out.split() == ["3600", "30"]
    assert main(["--total", "1h", "30s"]) == 0
    assert capsys.readouterr().out.split() == ["3630"]
