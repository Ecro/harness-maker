"""Phase 1 — autopilot dot-form entry (`python -m harness_maker.autopilot on/off`).

PLAN-command-surface-registry ADR-001/003: down-unify the lone Typer autopilot toggle to
the dominant dot-form, sharing one validation helper with the retained Typer alias.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import autopilot
from harness_maker.models import AtomicStage


def test_resolve_toggle_config_valid_defaults() -> None:
    level, stages = autopilot.resolve_toggle_config("auto_safe", None)
    assert level == "auto_safe"
    assert stages  # canonical default pipeline, non-empty
    assert all(isinstance(s, AtomicStage) for s in stages)


def test_resolve_toggle_config_custom_pipeline() -> None:
    _level, stages = autopilot.resolve_toggle_config("full", "research,plan")
    assert [s.value for s in stages] == ["research", "plan"]


def test_resolve_toggle_config_rejects_bad_level() -> None:
    with pytest.raises(ValueError, match="invalid --level"):
        autopilot.resolve_toggle_config("turbo", None)


def test_resolve_toggle_config_rejects_bad_pipeline() -> None:
    with pytest.raises(ValueError, match="invalid --pipeline"):
        autopilot.resolve_toggle_config("auto_safe", "research,bogus-stage")


def test_dotform_on_writes_then_off_clears(tmp_path: Path) -> None:
    rc = autopilot.main(
        ["on", "--level", "auto_safe", "--pipeline", "research,plan", "--root", str(tmp_path)]
    )
    assert rc == 0
    assert autopilot.load(tmp_path) is not None
    rc = autopilot.main(["off", "--root", str(tmp_path)])
    assert rc == 0
    assert autopilot.load(tmp_path) is None


def test_dotform_bad_level_returns_2_no_partial_marker(tmp_path: Path) -> None:
    rc = autopilot.main(["on", "--level", "turbo", "--root", str(tmp_path)])
    assert rc == 2
    assert autopilot.load(tmp_path) is None


def test_dotform_misroute_guard_redirects(capsys: pytest.CaptureFixture[str]) -> None:
    rc = autopilot.main(["boundary"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "not a subcommand" in err
    assert "python -m harness_maker.autopilot_caps boundary" in err


def test_cli_alias_and_dotform_reject_bad_level_identically(tmp_path: Path) -> None:
    # Shared-helper parity (ADR-003): the retained Typer alias and the dot-form entry
    # validate the same way — neither writes a marker on a bad level.
    from typer.testing import CliRunner

    from harness_maker.cli import app

    result = CliRunner().invoke(
        app, ["autopilot", "on", "--level", "turbo", "--root", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "invalid --level" in result.output
    assert autopilot.load(tmp_path) is None

    assert autopilot.main(["on", "--level", "turbo", "--root", str(tmp_path)]) == 2
    assert autopilot.load(tmp_path) is None
