"""Hidden tests for t17: error positions, while config.load still shows the bad text."""

import pytest
from timeparse import parse_duration
from timeparse.cli import main
from timeparse.config import ConfigError, load


def test_the_message_names_the_position() -> None:
    """Make `parse_duration`'s error messages say where the input went wrong, e.g. `invalid
    duration '1h3x': unexpected 'x' at position 3`.

    Source: prompt
    """
    with pytest.raises(ValueError) as info:
        parse_duration("1h3x")
    assert str(info.value) == "invalid duration '1h3x': unexpected 'x' at position 3"


def test_config_errors_keep_their_text() -> None:
    """A duration that is malformed shows its text in the message, so an operator can find it.

    Source: docs/config.md
    """
    with pytest.raises(ConfigError) as info:
        load("connect = 30s\ntimeout = 1h 30m\n")
    assert str(info.value) == "config line 2: bad duration '1h 30m'"
    with pytest.raises(ConfigError) as info:
        load("timeout = 1h 30m\n")
    assert str(info.value) == "config line 1: bad duration '1h 30m'"
    with pytest.raises(ConfigError) as info:
        load("# timeouts\nread = 2m\nidle = 45\nretry = 1h-30m\n")
    assert str(info.value) == "config line 4: bad duration '1h-30m'"


def test_the_cli_error_line_is_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    """Every other module keeps its current behaviour.

    Source: prompt
    """
    assert main(["1h", "1h 30m"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: invalid duration: '1h 30m'\n"
