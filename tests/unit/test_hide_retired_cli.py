"""SPEC-hide-retired-cli: retired commands leave help, keep working, and say they are retired."""

from __future__ import annotations

import re

import pytest
import typer.core
from typer.testing import CliRunner

from harness_maker.cli import app

runner = CliRunner(env={"COLUMNS": "200"})
#: A command row in either help format: Rich's boxed `│ make  …` or Click's plain `  make  …`.
_ROW = re.compile(r"^[│ ]\s*([a-z][\w-]*)\s{2,}\S")


def _commands(text: str) -> set[str]:
    names: set[str] = set()
    in_commands = False
    for line in text.splitlines():
        if re.match(r"^\W*Commands\b", line):
            in_commands = True
        elif in_commands and (match := _ROW.match(line)):
            names.add(match.group(1))
    return names


def test_ac_001_top_help_hides_the_retired_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    # CI renders Click's plain help, a terminal renders Rich's boxed help; both must hide them.
    outputs = [runner.invoke(app, ["--help"]).output]
    monkeypatch.setattr(typer.core, "HAS_RICH", False)
    outputs.append(runner.invoke(app, ["--help"]).output)
    for out in outputs:
        names = _commands(out)
        assert {"make", "health", "remove"} <= names, out
        assert not {"autopilot", "verify"} & names, out


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
