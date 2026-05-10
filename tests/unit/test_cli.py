"""Tests for harness_maker.cli --update flag (Phase 1, plugin-vs-generator-2026-05)."""

from __future__ import annotations

import json
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

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", return_value=MagicMock(files=[])),
        patch("harness_maker.cli.render"),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=_minimal_answers()),
        patch("harness_maker.cli.interview", interview_spy),
    ):
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

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", return_value=MagicMock(files=[])),
        patch("harness_maker.cli.render"),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli.interview", interview_spy),
    ):
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

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", return_value=MagicMock(files=[])),
        patch("harness_maker.cli.render"),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=_minimal_answers()),
        patch("harness_maker.cli.interview", interview_spy),
    ):
        result = runner.invoke(app, ["make", str(tmp_path)])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    interview_spy.assert_not_called()


# ---------------------------------------------------------------------------
# test_manifest_written_after_make (Phase 1: UX gaps)
# ---------------------------------------------------------------------------


def test_manifest_written_after_make(tmp_path: Path) -> None:
    """make() writes .claude/.harness-manifest.json with valid JSON listing file paths."""
    from harness_maker.models import Blueprint, FileEntry, HarnessConfig

    files = [
        FileEntry(
            path=Path("harness.yaml"),
            template="harness-yaml/Side.yaml.j2",
            context={"preset": "Side"},
            frontmatter={},
        ),
        FileEntry(
            path=Path("settings.json"),
            template="settings/Side.json.j2",
            context={"preset": "Side"},
            frontmatter={},
        ),
    ]
    bp = Blueprint(config=HarnessConfig(), files=files)
    written_paths = [tmp_path / ".claude" / "harness.yaml", tmp_path / ".claude" / "settings.json"]
    answers = _minimal_answers()

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", return_value=bp),
        patch("harness_maker.cli.render", return_value=written_paths),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=answers),
        patch("harness_maker.cli.interview", return_value=answers),
    ):
        (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
        result = runner.invoke(app, ["make", str(tmp_path)])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    manifest_path = tmp_path / ".claude" / ".harness-manifest.json"
    assert manifest_path.is_file(), ".harness-manifest.json must be written after make()"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["generated_by"] == "harness-maker"
    assert "version" in data
    assert isinstance(data["files"], list)
    assert len(data["files"]) >= 1


# ---------------------------------------------------------------------------
# Phase 2: CLI flags extension tests
# ---------------------------------------------------------------------------


def test_grade_threshold_flag(tmp_path: Path) -> None:
    """--grade-threshold=B overrides the default grade_threshold in answers."""
    _write_harness_yaml(tmp_path)
    answers = _minimal_answers()
    captured_bp = {}

    def _capture_synthesize(p, a, **kw):
        from harness_maker.models import Blueprint, HarnessConfig

        captured_bp["grade_threshold"] = a.grade_threshold
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=answers),
        patch("harness_maker.cli.interview", return_value=answers),
    ):
        result = runner.invoke(app, ["make", str(tmp_path), "--grade-threshold", "B"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert captured_bp["grade_threshold"] == "B"


def test_domains_flag(tmp_path: Path) -> None:
    """--domains=python,react sets answers.domains."""
    _write_harness_yaml(tmp_path)
    answers = _minimal_answers()
    captured_bp = {}

    def _capture_synthesize(p, a, **kw):
        from harness_maker.models import Blueprint, HarnessConfig

        captured_bp["domains"] = list(a.domains)
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=answers),
        patch("harness_maker.cli.interview", return_value=answers),
    ):
        result = runner.invoke(app, ["make", str(tmp_path), "--domains", "python,react"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert captured_bp["domains"] == ["python", "react"]


def test_mechanical_checks_flag(tmp_path: Path) -> None:
    """--mechanical-checks passes semicolon-separated commands."""
    _write_harness_yaml(tmp_path)
    answers = _minimal_answers()
    captured_bp = {}

    def _capture_synthesize(p, a, **kw):
        from harness_maker.models import Blueprint, HarnessConfig

        captured_bp["mechanical_checks"] = list(a.mechanical_checks)
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=answers),
        patch("harness_maker.cli.interview", return_value=answers),
    ):
        result = runner.invoke(
            app, ["make", str(tmp_path), "--mechanical-checks", "ruff check .;mypy ."]
        )

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert captured_bp["mechanical_checks"] == ["ruff check .", "mypy ."]


def test_focus_flag_adds_reviewers(tmp_path: Path) -> None:
    """--focus=security adds security-reviewer + security-auditor to Side preset."""
    _write_harness_yaml(tmp_path)
    answers = _minimal_answers()
    captured_bp = {}

    def _capture_synthesize(p, a, **kw):
        from harness_maker.models import Blueprint, HarnessConfig

        captured_bp["reviewers_enabled"] = list(a.reviewers["enabled"])
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=answers),
        patch("harness_maker.cli.interview", return_value=answers),
    ):
        result = runner.invoke(app, ["make", str(tmp_path), "--focus", "security"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    enabled = captured_bp["reviewers_enabled"]
    assert "security-reviewer" in enabled
    assert "security-auditor" in enabled


def test_preset_plus_extended_flags(tmp_path: Path) -> None:
    """Combo: --preset=Production --grade-threshold=A --domains=python all survive."""
    _write_harness_yaml(tmp_path)
    answers = _minimal_answers()
    captured_bp = {}

    def _capture_synthesize(p, a, **kw):
        from harness_maker.models import Blueprint, HarnessConfig

        captured_bp["grade_threshold"] = a.grade_threshold
        captured_bp["domains"] = list(a.domains)
        captured_bp["preset"] = a.preset
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=answers),
        patch("harness_maker.cli.interview", return_value=answers),
    ):
        result = runner.invoke(
            app,
            [
                "make",
                str(tmp_path),
                "--preset",
                "Production",
                "--grade-threshold",
                "A",
                "--domains",
                "python",
            ],
        )

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    from harness_maker.models import Preset

    assert captured_bp["preset"] == Preset.PRODUCTION
    assert captured_bp["grade_threshold"] == "A"
    assert captured_bp["domains"] == ["python"]


# ---------------------------------------------------------------------------
# Phase 5: dry-run + install summary tests
# ---------------------------------------------------------------------------


def test_dry_run_writes_no_files(tmp_path: Path) -> None:
    """--dry-run prints summary, writes no files, exits 0."""
    answers = _minimal_answers()

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize") as mock_synth,
        patch("harness_maker.cli.render") as mock_render,
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=None),
        patch("harness_maker.cli.interview", return_value=answers),
    ):
        from harness_maker.models import Blueprint, FileEntry, HarnessConfig

        files = [
            FileEntry(
                path=Path("harness.yaml"),
                template="harness-yaml/Side.yaml.j2",
                context={"preset": "Side"},
                frontmatter={},
            ),
        ]
        mock_synth.return_value = Blueprint(config=HarnessConfig(), files=files)
        mock_render.return_value = []
        result = runner.invoke(app, ["make", str(tmp_path), "--dry-run"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert "NEW:" in result.output or "new:" in result.output.lower()
    mock_render.assert_not_called()


def test_dry_run_format(tmp_path: Path) -> None:
    """--dry-run output contains category counts."""
    answers = _minimal_answers()

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize") as mock_synth,
        patch("harness_maker.cli.render") as mock_render,
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=None),
        patch("harness_maker.cli.interview", return_value=answers),
    ):
        from harness_maker.models import Blueprint, FileEntry, HarnessConfig

        files = [
            FileEntry(
                path=Path("harness.yaml"),
                template="harness-yaml/Side.yaml.j2",
                context={"preset": "Side"},
                frontmatter={},
            ),
        ]
        mock_synth.return_value = Blueprint(config=HarnessConfig(), files=files)
        mock_render.return_value = []
        result = runner.invoke(app, ["make", str(tmp_path), "--dry-run"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    output_lower = result.output.lower()
    assert "new" in output_lower


# ---------------------------------------------------------------------------
# Phase 6: partial override preservation test
# ---------------------------------------------------------------------------


def test_partial_override_preserves_unchanged_fields(tmp_path: Path) -> None:
    """Changing --grade-threshold=B must not reset --domains set in prior make."""
    _write_harness_yaml(tmp_path)
    answers = _minimal_answers().model_copy(
        update={"domains": ["python", "react"], "mechanical_checks": ["ruff check ."]}
    )
    captured_bp = {}

    def _capture_synthesize(p, a, **kw):
        from harness_maker.models import Blueprint, HarnessConfig

        captured_bp["domains"] = list(a.domains)
        captured_bp["mechanical_checks"] = list(a.mechanical_checks)
        captured_bp["grade_threshold"] = a.grade_threshold
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._emit_install_summary"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=answers),
        patch("harness_maker.cli.interview", return_value=answers),
    ):
        result = runner.invoke(
            app, ["make", str(tmp_path), "--grade-threshold", "B"]
        )

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert captured_bp["grade_threshold"] == "B"
    assert captured_bp["domains"] == ["python", "react"]
    assert captured_bp["mechanical_checks"] == ["ruff check ."]
