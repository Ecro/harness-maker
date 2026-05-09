"""Unit tests for harness_maker.hooks.loop_gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.hooks.loop_gate import _find_marker, _pretooluse, _stop_hook


class TestStopHook:
    def test_no_marker_exits_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        assert _stop_hook("") == 0

    def test_marker_present_exits_2_with_escape_hatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".hm-loop-active").touch()
        result = _stop_hook("")
        captured = capsys.readouterr()
        assert result == 2
        assert "rm .hm-loop-active" in captured.out
        # Must be valid JSON with decision=block
        payload = json.loads(captured.out)
        assert payload["decision"] == "block"

    def test_stop_hook_active_guard_exits_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".hm-loop-active").touch()
        # stop_hook_active guard must short-circuit even when marker exists
        assert _stop_hook('{"stop_hook_active": true}') == 0


class TestPreToolUse:
    def test_no_marker_exits_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        assert _pretooluse("") == 0

    def test_marker_present_still_exits_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".hm-loop-active").touch()
        # Cursor preToolUse is advisory only — must never block
        assert _pretooluse("") == 0


class TestFindMarker:
    def test_not_found_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        assert _find_marker(tmp_path) is None

    def test_found_in_cwd(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        marker = tmp_path / ".hm-loop-active"
        marker.touch()
        assert _find_marker(tmp_path) == marker

    def test_found_in_parent(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        marker = tmp_path / ".hm-loop-active"
        marker.touch()
        subdir = tmp_path / "sub"
        subdir.mkdir()
        assert _find_marker(subdir) == marker

    def test_git_as_file_stops_walk(self, tmp_path: Path) -> None:
        # Git worktrees have .git as a regular file, not a directory.
        # _find_marker must stop at this boundary the same way.
        (tmp_path / ".git").write_text("gitdir: /repo/.git/worktrees/wt1\n")
        subdir = tmp_path / "sub"
        subdir.mkdir()
        # No marker → should return None, not walk above tmp_path
        assert _find_marker(subdir) is None
