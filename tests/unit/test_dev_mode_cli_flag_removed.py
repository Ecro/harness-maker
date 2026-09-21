"""AC-007 (SPEC-dev-mode-removal): the CLI flag is gone from every entry point.

The four entry points are enumerated from the PRE-change tree (spec_machine.py `check` and
`waiver-check`, cli.py `make`, codex_setup.py) — a list produced by grepping the code this
change removes, so a parser that quietly keeps the flag is still checked. Each is driven
through its real argument parser: removal must be an argument ERROR, not a silently ignored
option.

`scripts/codex_engine.py` is a fifth site the SPEC did not enumerate. It FORWARDS the flag to
`harness-maker make`, so once `make` rejects it the Codex bootstrap would fail on every run
that passed one — it is pinned here for the same reason.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[2]


def _argparse_rejects(call: object) -> bool:
    with pytest.raises(SystemExit) as exc:
        call()  # type: ignore[operator]
    return exc.value.code == 2


def test_ac_007_flag_absent_from_every_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness_maker import codex_setup, spec_machine
    from harness_maker.cli import app

    yaml_path = tmp_path / "SPEC-x.machine.yaml"
    md_path = tmp_path / "SPEC-x.md"
    yaml_path.write_text("schema_version: 3\n", encoding="utf-8")
    md_path.write_text("---\n---\n", encoding="utf-8")

    check = ["check", "--all", "--yaml", str(yaml_path), "--md", str(md_path)]
    assert _argparse_rejects(lambda: spec_machine.main([*check, "--dev-mode", "spec-driven"]))

    waiver = ["waiver-check", "--yaml", str(yaml_path), "--root", str(tmp_path)]
    assert _argparse_rejects(lambda: spec_machine.main([*waiver, "--dev-mode", "task-driven"]))

    result = CliRunner().invoke(app, ["make", str(tmp_path), "--dev-mode", "spec-driven"])
    assert result.exit_code == 2, result.output

    monkeypatch.setattr(
        sys, "argv", ["codex_setup", "make", str(tmp_path), "--dev-mode", "spec-driven"]
    )
    assert _argparse_rejects(lambda: codex_setup.main(ROOT))


def test_ac_007_codex_engine_no_longer_forwards_the_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["codex_engine", str(tmp_path), "--expected", "0", "--dev-mode", "spec-driven"]
    )
    assert _argparse_rejects(
        lambda: runpy.run_path(str(ROOT / "scripts" / "codex_engine.py"), run_name="__main__")
    )


@pytest.mark.parametrize("color", [False, True], ids=["plain", "color"])
def test_ac_007_make_takes_a_strictness_override(color: bool) -> None:
    """`/hm:configure` is the only path to change strictness (ADR-007) and it drives `make`,
    so removing `--dev-mode` without a replacement would leave the knob unreachable."""
    from harness_maker.cli import app

    result = CliRunner().invoke(app, ["make", "--help"], color=color, env={"FORCE_COLOR": "1"})
    assert result.exit_code == 0, result.output
    # Rich may insert ANSI sequences between the two option-prefix hyphens.
    assert "--strictness" in unstyle(result.output)
