"""SPEC-hide-retired-cli: retired commands leave help, keep working, and say they are retired."""

from __future__ import annotations

from typer.testing import CliRunner

from harness_maker.cli import app

runner = CliRunner(env={"COLUMNS": "200"})


def _commands(text: str) -> set[str]:
    return {
        line.split()[1]
        for line in text.splitlines()
        if line.startswith("│ ") and len(line.split()) > 1
    }


def test_ac_001_top_help_hides_the_retired_commands() -> None:
    names = _commands(runner.invoke(app, ["--help"]).output)
    assert {"make", "health", "remove"} <= names
    assert not {"autopilot", "verify"} & names


def test_ac_001_make_help_hides_the_persistence_flag() -> None:
    out = runner.invoke(app, ["make", "--help"]).output
    assert "--autonomy-persistent" not in out
    assert "--autonomy-level" in out


def test_ac_001_autonomy_level_help_names_what_it_controls() -> None:
    out = runner.invoke(app, ["make", "--help"]).output
    assert "Autopilot auto-advance" not in out
    assert "auto_full" in out


def test_ac_001_hidden_commands_still_run_and_say_they_are_retired() -> None:
    for name in ("verify", "autopilot"):
        result = runner.invoke(app, [name, "--help"])
        assert result.exit_code == 0, name
        assert "Retired in 0.64.0" in " ".join(result.output.split()), name
