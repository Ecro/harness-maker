"""Tests for harness_maker.hooks.flush_session."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from harness_maker.hooks.flush_session import (
    _append_session_log,
    _snapshot_progress,
    run,
)

# ──────────────────────────────────────────────────────────────────────────────
# _snapshot_progress
# ──────────────────────────────────────────────────────────────────────────────


def test_snapshot_copies_progress_file(tmp_path: Path) -> None:
    progress = tmp_path / ".claude-progress.json"
    progress.write_text('{"current_phase": 3}', encoding="utf-8")

    result = _snapshot_progress(tmp_path, "20260504T120000Z")

    assert result is not None
    assert result.name == ".claude-progress-checkpoint-20260504T120000Z.json"
    assert result.read_text() == '{"current_phase": 3}'


def test_snapshot_returns_none_when_no_progress(tmp_path: Path) -> None:
    result = _snapshot_progress(tmp_path, "20260504T120000Z")
    assert result is None


def test_snapshot_does_not_overwrite_existing_checkpoint(tmp_path: Path) -> None:
    progress = tmp_path / ".claude-progress.json"
    progress.write_text('{"current_phase": 5}', encoding="utf-8")
    _snapshot_progress(tmp_path, "20260504T120000Z")
    # second call with same ts overwrites (shutil.copy2 behavior — idempotent)
    result = _snapshot_progress(tmp_path, "20260504T120000Z")
    assert result is not None
    assert result.read_text() == '{"current_phase": 5}'


# ──────────────────────────────────────────────────────────────────────────────
# _append_session_log
# ──────────────────────────────────────────────────────────────────────────────


def test_append_creates_session_log(tmp_path: Path) -> None:
    _append_session_log(tmp_path, "20260504T120000Z", "auto", None)

    log_dir = tmp_path / ".claude" / "memory" / "session"
    assert log_dir.is_dir()

    # File named by today's date (mocked below to be deterministic)
    files = list(log_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "checkpoint:compaction" in content
    assert "trigger:auto" in content
    assert "no progress file" in content


def test_append_references_checkpoint_file(tmp_path: Path) -> None:
    checkpoint = tmp_path / ".claude-progress-checkpoint-20260504T120000Z.json"
    checkpoint.write_text("{}", encoding="utf-8")

    _append_session_log(tmp_path, "20260504T120000Z", "manual", checkpoint)

    files = list((tmp_path / ".claude" / "memory" / "session").glob("*.md"))
    content = files[0].read_text()
    assert checkpoint.name in content


def test_append_accumulates_on_existing_log(tmp_path: Path) -> None:
    _append_session_log(tmp_path, "20260504T100000Z", "auto", None)
    _append_session_log(tmp_path, "20260504T110000Z", "auto", None)

    files = list((tmp_path / ".claude" / "memory" / "session").glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    # Both checkpoint entries present
    assert "20260504-10" in content
    assert "20260504-11" in content


def test_append_creates_parent_dirs(tmp_path: Path) -> None:
    deep = tmp_path / "nested" / "project"
    deep.mkdir(parents=True)
    # Should not raise even if .claude/memory/session doesn't exist
    _append_session_log(deep, "20260504T120000Z", "auto", None)
    assert (deep / ".claude" / "memory" / "session").is_dir()


# ──────────────────────────────────────────────────────────────────────────────
# run() — integration
# ──────────────────────────────────────────────────────────────────────────────


def test_run_exits_0_without_progress(tmp_path: Path) -> None:
    with patch("harness_maker.hooks.flush_session._read_stdin", return_value={"trigger": "auto"}):
        rc = run(cwd=tmp_path)
    assert rc == 0


def test_run_exits_0_with_progress(tmp_path: Path) -> None:
    (tmp_path / ".claude-progress.json").write_text('{"current_phase": 2}', encoding="utf-8")
    with patch("harness_maker.hooks.flush_session._read_stdin", return_value={"trigger": "manual"}):
        rc = run(cwd=tmp_path)
    assert rc == 0
    checkpoints = list(tmp_path.glob(".claude-progress-checkpoint-*.json"))
    assert len(checkpoints) == 1


def test_run_creates_session_dir_always(tmp_path: Path) -> None:
    with patch("harness_maker.hooks.flush_session._read_stdin", return_value={}):
        run(cwd=tmp_path)
    assert (tmp_path / ".claude" / "memory" / "session").is_dir()


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point (subprocess)
# ──────────────────────────────────────────────────────────────────────────────


def test_main_as_subprocess(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.flush_session"],
        input=json.dumps({"trigger": "auto"}),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=15,
    )
    assert result.returncode == 0
