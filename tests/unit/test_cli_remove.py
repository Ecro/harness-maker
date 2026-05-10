"""Tests for harness-maker remove subcommand (Phase 7, make-ux-gaps-2026-05)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from harness_maker.cli import app

runner = CliRunner()


def _scaffold_project(tmp_path: Path) -> Path:
    """Create a minimal post-make project layout with manifest + files."""
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)

    manifest_files = [
        "harness.yaml",
        "agents/code-reviewer.md",
        "agents/security-reviewer.md",
        "commands/hm/execute.md",
        "hooks/hooks.json",
        "settings.json",
    ]
    manifest = {
        "generated_by": "harness-maker",
        "version": "0.7.4",
        "files": manifest_files,
    }
    (claude / ".harness-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    (claude / "harness.yaml").write_text(
        "---\nharness_maker_version: 0.7.4\npreset: Side\n---\npreset: Side\n",
        encoding="utf-8",
    )
    (claude / "agents").mkdir(exist_ok=True)
    (claude / "agents" / "code-reviewer.md").write_text(
        "---\ngenerated_by: harness-maker\ncontent_hash: abc\n---\ncode reviewer",
        encoding="utf-8",
    )
    (claude / "agents" / "security-reviewer.md").write_text(
        "---\ngenerated_by: harness-maker\ncontent_hash: def\n---\nsecurity reviewer",
        encoding="utf-8",
    )
    (claude / "commands" / "hm").mkdir(parents=True)
    (claude / "commands" / "hm" / "execute.md").write_text(
        "---\ngenerated_by: harness-maker\n---\nexecute command",
        encoding="utf-8",
    )
    (claude / "hooks").mkdir(exist_ok=True)
    (claude / "hooks" / "hooks.json").write_text(
        '{"hooks": []}', encoding="utf-8"
    )
    (claude / "settings.json").write_text(
        '{"permissions": {}}', encoding="utf-8"
    )
    return tmp_path


def _scaffold_with_user_block(tmp_path: Path) -> Path:
    """Project where one agent file has @hm:user: markers."""
    _scaffold_project(tmp_path)
    claude = tmp_path / ".claude"
    (claude / "agents" / "code-reviewer.md").write_text(
        "---\ngenerated_by: harness-maker\ncontent_hash: abc\n---\n"
        "code reviewer\n"
        "<!-- @hm:user:extensions -->\n"
        "my custom stuff\n"
        "<!-- @hm:/user:extensions -->\n",
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# remove: managed files deleted
# ---------------------------------------------------------------------------


def test_remove_deletes_managed_files(tmp_path: Path) -> None:
    """remove deletes all manifest-listed files except harness.yaml."""
    project = _scaffold_project(tmp_path)
    claude = project / ".claude"

    result = runner.invoke(app, ["remove", str(project)])
    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"

    assert not (claude / "agents" / "code-reviewer.md").exists()
    assert not (claude / "agents" / "security-reviewer.md").exists()
    assert not (claude / "commands" / "hm" / "execute.md").exists()
    assert not (claude / "hooks" / "hooks.json").exists()
    assert not (claude / "settings.json").exists()


# ---------------------------------------------------------------------------
# remove: harness.yaml kept by default
# ---------------------------------------------------------------------------


def test_remove_keeps_harness_yaml(tmp_path: Path) -> None:
    """harness.yaml is preserved unless --remove-yaml is passed."""
    project = _scaffold_project(tmp_path)
    claude = project / ".claude"

    result = runner.invoke(app, ["remove", str(project)])
    assert result.exit_code == 0

    assert (claude / "harness.yaml").exists()


# ---------------------------------------------------------------------------
# remove: --remove-yaml deletes harness.yaml
# ---------------------------------------------------------------------------


def test_remove_yaml_flag(tmp_path: Path) -> None:
    """--remove-yaml also deletes harness.yaml."""
    project = _scaffold_project(tmp_path)
    claude = project / ".claude"

    result = runner.invoke(app, ["remove", str(project), "--remove-yaml"])
    assert result.exit_code == 0

    assert not (claude / "harness.yaml").exists()


# ---------------------------------------------------------------------------
# remove: user-block files skipped
# ---------------------------------------------------------------------------


def test_remove_skips_user_block_files(tmp_path: Path) -> None:
    """Files with @hm:user: markers are skipped with a warning."""
    project = _scaffold_with_user_block(tmp_path)
    claude = project / ".claude"

    result = runner.invoke(app, ["remove", str(project)])
    assert result.exit_code == 0

    assert (claude / "agents" / "code-reviewer.md").exists()
    assert "skipped" in result.output.lower() or "user" in result.output.lower()


def test_remove_deletes_files_with_empty_user_block_placeholders(tmp_path: Path) -> None:
    """Generated placeholder markers alone are not user customization."""
    project = _scaffold_project(tmp_path)
    claude = project / ".claude"
    target = claude / "commands" / "hm" / "execute.md"
    target.write_text(
        "---\ngenerated_by: harness-maker\n---\n"
        "execute command\n"
        "<!-- @hm:user:extensions -->\n"
        "<!-- Project-specific overrides. Preserved across upgrades. -->\n"
        "<!-- @hm:/user:extensions -->\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["remove", str(project)])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert not target.exists()


# ---------------------------------------------------------------------------
# remove: --dry-run prints but does not delete
# ---------------------------------------------------------------------------


def test_remove_dry_run(tmp_path: Path) -> None:
    """--dry-run shows what would be removed but deletes nothing."""
    project = _scaffold_project(tmp_path)
    claude = project / ".claude"

    result = runner.invoke(app, ["remove", str(project), "--dry-run"])
    assert result.exit_code == 0

    assert (claude / "agents" / "code-reviewer.md").exists()
    assert (claude / "agents" / "security-reviewer.md").exists()
    assert (claude / "hooks" / "hooks.json").exists()


# ---------------------------------------------------------------------------
# remove: manifest missing → graceful error
# ---------------------------------------------------------------------------


def test_remove_no_manifest(tmp_path: Path) -> None:
    """remove without .harness-manifest.json exits with error."""
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)
    (claude / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")

    result = runner.invoke(app, ["remove", str(tmp_path)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# remove: summary output
# ---------------------------------------------------------------------------


def test_remove_prints_summary(tmp_path: Path) -> None:
    """remove prints a summary of removed/skipped files."""
    project = _scaffold_with_user_block(tmp_path)

    result = runner.invoke(app, ["remove", str(project)])
    assert result.exit_code == 0
    lower = result.output.lower()
    assert "removed" in lower or "deleted" in lower
