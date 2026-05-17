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
        patch(
            "harness_maker.cli.sweep_orphans",
            return_value=MagicMock(deleted=[], kept=[]),
        ),
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
    assert ".claude/harness.yaml" in data["files"]
    assert all(not Path(p).is_absolute() for p in data["files"])


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
        result = runner.invoke(app, ["make", str(tmp_path), "--grade-threshold", "B"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert captured_bp["grade_threshold"] == "B"
    assert captured_bp["domains"] == ["python", "react"]
    assert captured_bp["mechanical_checks"] == ["ruff check ."]


# ---------------------------------------------------------------------------
# wrapup_docs CLI flag test
# ---------------------------------------------------------------------------


def test_wrapup_docs_flag(tmp_path: Path) -> None:
    """--wrapup-docs passes semicolon-separated paths to answers."""
    _write_harness_yaml(tmp_path)
    captured: dict[str, object] = {}

    def _capture(p, a, **kw):
        from harness_maker.models import Blueprint, HarnessConfig

        captured["wrapup_docs"] = list(a.wrapup_docs)
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._emit_install_summary"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch(
            "harness_maker.cli.answers_from_harness_yaml",
            return_value=_minimal_answers(),
        ),
        patch("harness_maker.cli.interview", return_value=_minimal_answers()),
    ):
        result = runner.invoke(
            app,
            [
                "make",
                str(tmp_path),
                "--wrapup-docs",
                "CHANGELOG.md;TODO.md",
            ],
        )

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert captured["wrapup_docs"] == ["CHANGELOG.md", "TODO.md"]


# ---------------------------------------------------------------------------
# security-scan CLI command
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 0.13.0 health-consolidation Phase 1: subcommand surface
# ---------------------------------------------------------------------------


def _registered_subcommand_names() -> set[str]:
    """All names typer has registered on the cli app — sourced via the
    underlying Click context. Using the public CLI introspection keeps the
    assertion meaningful even if typer's internal layout changes."""
    from typer.main import get_command

    cmd = get_command(app)
    if not hasattr(cmd, "commands"):
        return set()
    return set(cmd.commands.keys())


def test_ai_readiness_subcommand_removed() -> None:
    """ADR-003: /hm:ai-readiness is removed atomically in 0.13.0."""
    names = _registered_subcommand_names()
    assert "ai-readiness" not in names, (
        f"ai-readiness must be removed in 0.13.0; got {sorted(names)}"
    )
    assert "ai-readiness-finalize" not in names, (
        f"ai-readiness-finalize must be removed in 0.13.0; got {sorted(names)}"
    )


def test_health_subcommand_registered() -> None:
    """/hm:health is the only audit-style command in 0.13.0."""
    names = _registered_subcommand_names()
    assert "health" in names, f"health must be registered; got {sorted(names)}"
    assert "health-finalize" in names, f"health-finalize must be registered; got {sorted(names)}"


def test_health_runs_against_minimal_project(tmp_path: Path) -> None:
    """Smoke test the unified entrypoint end-to-end on tmp_path."""
    _write_harness_yaml(tmp_path)
    result = runner.invoke(app, ["health", str(tmp_path), "--no-update-dashboard"])
    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert "health: structural=" in result.output
    assert "personalization=" in result.output


def test_health_writes_three_section_dashboard(tmp_path: Path) -> None:
    """End-to-end: health → dashboard.md contains all three sections."""
    _write_harness_yaml(tmp_path)
    result = runner.invoke(app, ["health", str(tmp_path)])
    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    dashboard = tmp_path / ".claude" / "observability" / "dashboard.md"
    assert dashboard.is_file()
    body = dashboard.read_text(encoding="utf-8")
    assert "## Structural" in body
    assert "## External risks" in body
    assert "## Personalization" in body


def test_security_scan_command_reports_findings(tmp_path: Path) -> None:
    """Generated security-scanner skill calls `cli security-scan`; keep it wired."""
    from harness_maker.models import Finding

    finding = Finding(
        severity="medium",
        category="prompt_injection",
        file="README.md",
        line=1,
        evidence="ignore previous instructions",
        fix="Remove the instruction override.",
    )

    with patch("harness_maker.security_scanner.scan_all", return_value=[finding]) as scan:
        result = runner.invoke(app, ["security-scan", str(tmp_path)])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    scan.assert_called_once()
    assert "Security scan: 1 finding" in result.output
    assert "prompt_injection" in result.output


def test_security_scan_blocks_high_when_policy_blocks(tmp_path: Path) -> None:
    """Production harness policy can make high findings fail the command."""
    from harness_maker.models import Finding

    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text(
        "---\ngenerated_by: harness-maker\n---\nsecurity:\n  on_finding:\n    high: block\n",
        encoding="utf-8",
    )
    finding = Finding(
        severity="high",
        category="secrets",
        file="leak.py",
        line=1,
        evidence="secret",
        fix="Rotate and remove.",
    )

    with patch("harness_maker.security_scanner.scan_all", return_value=[finding]):
        result = runner.invoke(app, ["security-scan", str(tmp_path)])

    assert result.exit_code == 1, f"expected blocking exit:\n{result.output}"
    assert "high secrets" in result.output


# ---------------------------------------------------------------------------
# real temporary project lifecycle
# ---------------------------------------------------------------------------


def test_make_update_clear_and_remove_real_tmp_project(tmp_path: Path) -> None:
    """Install, update, clear config-style lists, dry-run remove, then remove."""
    result = runner.invoke(
        app,
        [
            "make",
            str(tmp_path),
            "--autoloop",
            "--grade-threshold",
            "B",
            "--domains",
            "python,react",
            "--mechanical-checks",
            "ruff check .",
            "--wrapup-docs",
            "CHANGELOG.md;TODO.md",
        ],
    )
    assert result.exit_code == 0, f"fresh make failed:\n{result.output}"

    claude = tmp_path / ".claude"
    assert (claude / "harness.yaml").is_file()
    assert (claude / ".harness-manifest.json").is_file()
    assert (claude / "commands" / "hm" / "make.md").is_file()
    assert (claude / "commands" / "hm" / "configure.md").is_file()
    assert (claude / "commands" / "hm" / "uninstall.md").is_file()

    update = runner.invoke(
        app,
        [
            "make",
            str(tmp_path),
            "--update",
            "--grade-threshold",
            "C",
            "--domains",
            "",
            "--mechanical-checks",
            "",
            "--wrapup-docs",
            "",
        ],
    )
    assert update.exit_code == 0, f"update failed:\n{update.output}"

    from harness_maker.interview import answers_from_harness_yaml

    reused = answers_from_harness_yaml(claude / "harness.yaml")
    assert reused is not None
    assert reused.grade_threshold == "C"
    assert reused.domains == []
    assert reused.mechanical_checks == []
    assert reused.wrapup_docs == []

    dry_run = runner.invoke(app, ["remove", str(tmp_path), "--dry-run"])
    assert dry_run.exit_code == 0, f"dry-run remove failed:\n{dry_run.output}"
    assert (claude / "commands" / "hm" / "make.md").is_file()

    remove = runner.invoke(app, ["remove", str(tmp_path)])
    assert remove.exit_code == 0, f"remove failed:\n{remove.output}"
    assert (claude / "harness.yaml").is_file()
    assert not (claude / ".harness-manifest.json").exists()
    assert not (claude / "commands" / "hm" / "make.md").exists()


# ---------------------------------------------------------------------------
# Phase 3 — configure-second-brain CLI subcommand (ADR-003)
# ---------------------------------------------------------------------------


def _write_provenance_harness_yaml(project: Path, body: str) -> None:
    """Mirror the renderer's provenance-frontmatter shape for fixture parity."""
    claude = project / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    frontmatter = (
        "---\n"
        "generated_by: harness-maker\n"
        "harness_maker_version: 0.13.0\n"
        "generated_at: '2026-01-01T00:00:00+00:00'\n"
        "source_template: harness-yaml/Side.yaml.j2\n"
        "provenance: official\n"
        "content_hash: " + "0" * 64 + "\n"
        "---\n"
    )
    (claude / "harness.yaml").write_text(frontmatter + body, encoding="utf-8")


def test_configure_second_brain_check_emits_guidance_when_folders_empty(
    tmp_path: Path,
) -> None:
    """--check on a folders=[] harness.yaml returns JSON with folders_empty=true."""
    body = (
        "preset: Side\n"
        "second_brain:\n"
        "  enabled: true\n"
        "  vault_path: /tmp/vault\n"
        "  project_id: harness-maker\n"
        "  folders: []\n"
    )
    _write_provenance_harness_yaml(tmp_path, body)

    result = runner.invoke(app, ["configure-second-brain", str(tmp_path), "--check"])

    assert result.exit_code == 0, result.output
    guidance = json.loads(result.output)
    assert guidance["folders_empty"] is True
    assert guidance["folder_count"] == 0
    assert guidance["default_suggestion"] == "99_HM/harness-maker"
    assert guidance["enabled"] is True


def test_configure_second_brain_check_reports_existing_folder(tmp_path: Path) -> None:
    """--check on a populated config reports folders_empty=False."""
    body = (
        "preset: Side\n"
        "second_brain:\n"
        "  enabled: true\n"
        "  vault_path: /tmp/vault\n"
        "  project_id: harness-maker\n"
        "  folders:\n"
        "    - path: 99_HM/harness-maker\n"
        "      read: true\n"
        "      write: true\n"
    )
    _write_provenance_harness_yaml(tmp_path, body)

    result = runner.invoke(app, ["configure-second-brain", str(tmp_path), "--check"])

    assert result.exit_code == 0, result.output
    guidance = json.loads(result.output)
    assert guidance["folders_empty"] is False
    assert guidance["folder_count"] == 1


def test_configure_second_brain_add_folder_writes_entry(tmp_path: Path) -> None:
    """--add-folder appends a writable folder entry to harness.yaml."""
    body = (
        "preset: Side\n"
        "second_brain:\n"
        "  enabled: true\n"
        "  vault_path: /tmp/vault\n"
        "  project_id: harness-maker\n"
        "  folders: []\n"
    )
    _write_provenance_harness_yaml(tmp_path, body)

    result = runner.invoke(
        app,
        [
            "configure-second-brain",
            str(tmp_path),
            "--add-folder",
            "99_HM/harness-maker",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["added"] == "99_HM/harness-maker"
    assert payload["folder_count"] == 1

    # Re-running --check after the write reports folders_empty=False.
    check = runner.invoke(app, ["configure-second-brain", str(tmp_path), "--check"])
    assert check.exit_code == 0
    assert json.loads(check.output)["folders_empty"] is False


def test_configure_second_brain_errors_when_harness_yaml_missing(
    tmp_path: Path,
) -> None:
    """Missing harness.yaml → exit 2 with JSON error (ADR-003 — actionable failure)."""
    result = runner.invoke(app, ["configure-second-brain", str(tmp_path), "--check"])

    assert result.exit_code == 2
    payload = json.loads(result.stderr if hasattr(result, "stderr") else result.output)
    assert "no harness.yaml" in payload.get("error", "")


def test_configure_second_brain_requires_a_subcommand_flag(tmp_path: Path) -> None:
    """Invoking with neither --check nor --add-folder fails with exit 2."""
    body = "preset: Side\nsecond_brain:\n  enabled: false\n"
    _write_provenance_harness_yaml(tmp_path, body)

    result = runner.invoke(app, ["configure-second-brain", str(tmp_path)])

    assert result.exit_code == 2
    # message is on stderr, but typer's CliRunner mixes streams by default
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert "--check" in combined or "--add-folder" in combined


def test_configure_second_brain_add_folder_is_idempotent(tmp_path: Path) -> None:
    """REVIEW-2026-05-17 P2: --add-folder must dedupe, not append a duplicate."""
    body = (
        "preset: Side\n"
        "second_brain:\n"
        "  enabled: true\n"
        "  vault_path: /tmp/vault\n"
        "  project_id: harness-maker\n"
        "  folders: []\n"
    )
    _write_provenance_harness_yaml(tmp_path, body)

    args = ["configure-second-brain", str(tmp_path), "--add-folder", "99_HM/harness-maker"]
    first = runner.invoke(app, args)
    assert first.exit_code == 0
    assert json.loads(first.output)["folder_count"] == 1

    second = runner.invoke(app, args)
    assert second.exit_code == 0
    payload = json.loads(second.output)
    assert payload.get("already_present") == "99_HM/harness-maker"
    assert payload["folder_count"] == 1


def test_configure_second_brain_add_folder_refreshes_content_hash(
    tmp_path: Path,
) -> None:
    """REVIEW-2026-05-17 P1: content_hash must match the new body so the
    reconciler does not silently mark harness.yaml as user-modified.
    """
    import hashlib

    import yaml as _yaml

    body = (
        "preset: Side\n"
        "second_brain:\n"
        "  enabled: true\n"
        "  vault_path: /tmp/vault\n"
        "  project_id: harness-maker\n"
        "  folders: []\n"
    )
    _write_provenance_harness_yaml(tmp_path, body)

    result = runner.invoke(
        app,
        [
            "configure-second-brain",
            str(tmp_path),
            "--add-folder",
            "99_HM/harness-maker",
        ],
    )
    assert result.exit_code == 0, result.output

    text = (tmp_path / ".claude" / "harness.yaml").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    raw_fm = _yaml.safe_load(text[4:end])
    raw_body = text[end + len("\n---\n") :]
    expected_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()
    assert raw_fm["content_hash"] == expected_hash, (
        f"content_hash in frontmatter ({raw_fm['content_hash']!r}) must equal "
        f"sha256(body) ({expected_hash!r}); stale hash blocks reconciler re-render"
    )
