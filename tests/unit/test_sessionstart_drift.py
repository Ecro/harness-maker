"""Tests for harness_maker.hooks.sessionstart_drift."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from harness_maker.hooks.sessionstart_drift import _format_context, run

# Pin both the imported __version__ AND latest_installed_version to a stable
# value so this test suite is deterministic regardless of what's actually in
# ~/.claude/plugins/cache/ (0.6.2 P6 alignment surfaced this).
_TEST_CURRENT = "0.5.5"


def _write_harness_yaml(project_dir: Path, stamped_version: str) -> None:
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    fm = f"---\nharness_maker_version: {stamped_version}\npreset: Side\n---\npreset: Side\n"
    (claude / "harness.yaml").write_text(fm, encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# run() — silent paths
# ──────────────────────────────────────────────────────────────────────────────


def test_run_silent_when_no_harness_yaml(tmp_path: Path, capsys) -> None:
    rc = run(cwd=tmp_path)
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_run_silent_when_versions_match(tmp_path: Path, capsys) -> None:
    _write_harness_yaml(tmp_path, _TEST_CURRENT)
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_run_silent_when_harness_yaml_has_no_frontmatter(tmp_path: Path, capsys) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    rc = run(cwd=tmp_path)
    assert rc == 0
    assert capsys.readouterr().out == ""


# ──────────────────────────────────────────────────────────────────────────────
# run() — drift surfaced
# ──────────────────────────────────────────────────────────────────────────────


def test_run_emits_additional_context_on_upgrade(tmp_path: Path, capsys) -> None:
    _write_harness_yaml(tmp_path, "0.0.1")
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "harness-maker drift" in ctx
    assert "0.0.1" in ctx
    assert _TEST_CURRENT in ctx
    assert "/harness-maker:make" in ctx


def test_run_emits_downgrade_warning(tmp_path: Path, capsys) -> None:
    _write_harness_yaml(tmp_path, "999.0.0")
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "downgrade" in ctx.lower()


def test_run_does_not_emit_system_message(tmp_path: Path, capsys) -> None:
    """systemMessage is NOT emitted (0.11.5).

    Per official Claude Code docs (2026-05-13), SessionStart hooks have no
    user-visible output field — both ``additionalContext`` and
    ``systemMessage`` feed Claude's context only. The 0.11.3 attempt to
    split into a "user-facing systemMessage" was based on a misreading of
    the spec. The replacement strategy: an imperative phrasing in
    ``additionalContext`` that tells Claude to surface the drift in its
    first response. Test guards against the dead field returning silently.
    """
    _write_harness_yaml(tmp_path, "0.0.1")
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "systemMessage" not in payload["hookSpecificOutput"]


def test_additional_context_is_imperative(tmp_path: Path, capsys) -> None:
    """additionalContext must instruct Claude to surface drift to the user.

    Descriptive phrasing ("drift detected: ...") is too easy to ignore.
    The text must contain explicit instruction to mention the drift in
    Claude's next response so the user actually finds out.
    """
    _write_harness_yaml(tmp_path, "0.0.1")
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        run(cwd=tmp_path)
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    # Imperative markers that prompt Claude to surface the drift.
    assert "TELL THE USER" in ctx
    assert "Tell the user" in ctx


# ──────────────────────────────────────────────────────────────────────────────
# _format_context
# ──────────────────────────────────────────────────────────────────────────────


def test_format_context_upgrade_mentions_make_command() -> None:
    msg = _format_context("0.4.0", "0.5.5", "upgrade")
    assert "/harness-maker:make" in msg
    assert "0.4.0" in msg
    assert "0.5.5" in msg


def test_format_context_downgrade_warns_intent() -> None:
    msg = _format_context("0.5.5", "0.4.0", "downgrade")
    assert "downgrade" in msg.lower()


def test_message_contains_update_flag() -> None:
    """Upgrade message mentions `make --update` so users know the fast re-render command."""
    msg = _format_context("0.4.0", "0.5.5", "upgrade")
    assert "make --update" in msg, (
        f"Expected 'make --update' as actionable command in message:\n{msg}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point — proves module is invokable as `python -m`
# ──────────────────────────────────────────────────────────────────────────────


def test_main_as_subprocess_silent_when_no_harness(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.sessionstart_drift"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=15,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_main_as_subprocess_emits_on_drift(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.0.1")
    result = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.sessionstart_drift"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=15,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
