"""`harness-maker detect-tools` as an external contract, exercised through Typer.

The unit tests cover the detection function. These cover the things a module-level test
structurally cannot see: that the command is registered under the name the slash command
types, that stdout is exactly one JSON object (the slash command parses it), that
diagnostics do not contaminate that stdout, and that the answer does not depend on which
directory the caller happened to be in.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness_maker import tool_detect
from harness_maker.cli import app

runner = CliRunner()


def _fake_which(present: set[str]) -> object:
    def _which(cmd: str) -> str | None:
        return f"/usr/bin/{cmd}" if cmd in present else None

    return _which


def test_the_command_is_registered_under_the_name_the_slash_command_types() -> None:
    names = {
        info.name or (info.callback.__name__.replace("_", "-") if info.callback else "")
        for info in app.registered_commands
    }
    assert "detect-tools" in names, sorted(names)


def test_stdout_is_exactly_one_json_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which({"codex"}))
    result = runner.invoke(app, ["detect-tools", "--json"])
    assert result.exit_code == 0, result.output

    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, lines
    payload = json.loads(lines[0])
    assert payload == {
        "codex": {"installed": True},
        "antigravity": {"installed": False},
        "cursor": {"installed": False},
    }


def test_the_json_payload_survives_a_diagnostic_on_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stdout must stay machine-readable even when the command has something to say.

    Mixing the two is how a consumer that does `json.loads(stdout)` starts failing for a
    reason that has nothing to do with detection.
    """
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which(set()))
    result = runner.invoke(app, ["detect-tools", "--json"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    json.loads(result.stdout.strip())


def test_the_result_does_not_depend_on_the_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which({"agy"}))
    first = runner.invoke(app, ["detect-tools", "--json"])

    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    second = runner.invoke(app, ["detect-tools", "--json"])

    assert first.exit_code == second.exit_code == 0
    assert json.loads(first.stdout.strip()) == json.loads(second.stdout.strip())
    assert json.loads(second.stdout.strip())["antigravity"] == {"installed": True}


def test_the_human_readable_form_names_both_the_key_and_the_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without `--json` a person reads this, and `antigravity` vs `agy` is the confusion.

    It must also never claim the tool is usable — `shutil.which` says the binary exists,
    not that `codex login` / `agy` auth has been done (PLAN ADR-001, §detect-tools contract).
    """
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which({"agy"}))
    result = runner.invoke(app, ["detect-tools"])
    assert result.exit_code == 0, result.output
    out = result.stdout
    assert "antigravity" in out
    assert "agy" in out
    assert "authentication" in out.lower() or "not verified" in out.lower()
