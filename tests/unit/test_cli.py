"""Tests for harness_maker.cli --update flag (Phase 1, plugin-vs-generator-2026-05)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from harness_maker.cli import app

runner = CliRunner()


def _minimal_answers():
    from harness_maker.interview import _build_answers
    from harness_maker.models import AtomicStage, DevMode, Preset, Target

    return _build_answers(
        locale="en",
        targets=[Target.CLAUDE_CODE],
        preset=Preset.SIDE,
        dev_mode=DevMode.TASK_DRIVEN,
        fused_workflows={
            "exec-rev-wrap": [AtomicStage.EXECUTE, AtomicStage.REVIEW, AtomicStage.WRAPUP]
        },
        default_workflow="exec-rev-wrap",
    )


def _write_harness_yaml(project: Path) -> None:
    claude = project / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        "---\nharness_maker_version: 0.1.0\npreset: Side\n---\npreset: Side\n",
        encoding="utf-8",
    )


def _all_patches(*, interview_spy: MagicMock | None = None, answers=None):
    """Return a list of patches that silence all downstream effects of make()."""
    _answers = answers if answers is not None else _minimal_answers()
    patches = [
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", return_value=MagicMock(files=[])),
        patch("harness_maker.cli.render"),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=_answers),
    ]
    if interview_spy is not None:
        patches.append(patch("harness_maker.cli.interview", interview_spy))
    else:
        patches.append(patch("harness_maker.cli.interview", return_value=_answers))
    return patches


# ---------------------------------------------------------------------------
# test_update_flag_with_harness_yaml
# ---------------------------------------------------------------------------


def test_update_flag_with_harness_yaml(tmp_path: Path) -> None:
    """--update re-renders silently when harness.yaml present; interview not called."""
    _write_harness_yaml(tmp_path)
    interview_spy = MagicMock(return_value=_minimal_answers())

    with patch("harness_maker.cli.profile", return_value=MagicMock()), \
         patch("harness_maker.cli.synthesize", return_value=MagicMock(files=[])), \
         patch("harness_maker.cli.render"), \
         patch("harness_maker.cli.verify", return_value=[]), \
         patch("harness_maker.cli.backup"), \
         patch("harness_maker.cli.reconcile", return_value=[]), \
         patch("harness_maker.cli._emit_post_make_readiness"), \
         patch("harness_maker.cli._emit_refdocs_index_build"), \
         patch("harness_maker.cli.answers_from_harness_yaml", return_value=_minimal_answers()), \
         patch("harness_maker.cli.interview", interview_spy):
        result = runner.invoke(app, ["make", str(tmp_path), "--update"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    interview_spy.assert_not_called()


# ---------------------------------------------------------------------------
# test_update_flag_without_harness_yaml
# ---------------------------------------------------------------------------


def test_update_flag_without_harness_yaml(tmp_path: Path) -> None:
    """--update exits 1 with a message referencing harness.yaml when file absent."""
    # Do NOT create harness.yaml in tmp_path — early-exit fires before profile()
    with patch("harness_maker.cli.profile", return_value=MagicMock()):
        result = runner.invoke(app, ["make", str(tmp_path), "--update"])

    assert result.exit_code == 1, f"exit {result.exit_code}:\n{result.output}"
    assert "harness.yaml" in result.output.lower(), (
        f"Expected 'harness.yaml' in output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# test_update_reinterview_precedence
# ---------------------------------------------------------------------------


def test_update_reinterview_precedence(tmp_path: Path) -> None:
    """--update --reinterview: --reinterview wins; interview() is called."""
    _write_harness_yaml(tmp_path)
    answers = _minimal_answers()
    interview_spy = MagicMock(return_value=answers)

    with patch("harness_maker.cli.profile", return_value=MagicMock()), \
         patch("harness_maker.cli.synthesize", return_value=MagicMock(files=[])), \
         patch("harness_maker.cli.render"), \
         patch("harness_maker.cli.verify", return_value=[]), \
         patch("harness_maker.cli.backup"), \
         patch("harness_maker.cli.reconcile", return_value=[]), \
         patch("harness_maker.cli._emit_post_make_readiness"), \
         patch("harness_maker.cli._emit_refdocs_index_build"), \
         patch("harness_maker.cli.interview", interview_spy):
        runner.invoke(app, ["make", str(tmp_path), "--update", "--reinterview"])

    interview_spy.assert_called_once()


# ---------------------------------------------------------------------------
# test_no_update_still_works  (regression guard)
# ---------------------------------------------------------------------------


def test_no_flag_reuses_harness_yaml(tmp_path: Path) -> None:
    """Regression guard: no-flag make still re-renders silently when harness.yaml exists.

    Named without 'update' so it is excluded from Phase B RED gate (-k update).
    """
    _write_harness_yaml(tmp_path)
    interview_spy = MagicMock(return_value=_minimal_answers())

    with patch("harness_maker.cli.profile", return_value=MagicMock()), \
         patch("harness_maker.cli.synthesize", return_value=MagicMock(files=[])), \
         patch("harness_maker.cli.render"), \
         patch("harness_maker.cli.verify", return_value=[]), \
         patch("harness_maker.cli.backup"), \
         patch("harness_maker.cli.reconcile", return_value=[]), \
         patch("harness_maker.cli._emit_post_make_readiness"), \
         patch("harness_maker.cli._emit_refdocs_index_build"), \
         patch("harness_maker.cli.answers_from_harness_yaml", return_value=_minimal_answers()), \
         patch("harness_maker.cli.interview", interview_spy):
        result = runner.invoke(app, ["make", str(tmp_path)])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    interview_spy.assert_not_called()
