"""worktree.py session-scoped marker content schema (loop-marker-session-scoping P2)."""

from __future__ import annotations

from pathlib import Path

from harness_maker import loop_marker, worktree


def _claude_dir(base: Path) -> Path:
    d = base / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    return d


class TestLoopModeActiveCli:
    def test_inactive_no_marker(self, tmp_path: Path) -> None:
        _claude_dir(tmp_path)
        rc = worktree.main(
            ["loop-mode-active", str(tmp_path), "--claude-session-id", "deadbeefcafe"]
        )
        assert rc == 1

    def test_active_on_content_match(self, tmp_path: Path) -> None:
        claude = _claude_dir(tmp_path)
        (claude / ".hm-loop-execute-1").write_text(
            loop_marker.format_marker_content("deadbeefcafe", [tmp_path]), encoding="utf-8"
        )
        rc = worktree.main(
            ["loop-mode-active", str(tmp_path), "--claude-session-id", "deadbeefcafe"]
        )
        assert rc == 0

    def test_inactive_other_session(self, tmp_path: Path) -> None:
        claude = _claude_dir(tmp_path)
        (claude / ".hm-loop-execute-1").write_text(
            loop_marker.format_marker_content("aaaaaaaaaaaa", [tmp_path]), encoding="utf-8"
        )
        rc = worktree.main(
            ["loop-mode-active", str(tmp_path), "--claude-session-id", "bbbbbbbbbbbb"]
        )
        assert rc == 1

    def test_valid_id_ignores_legacy_global(self, tmp_path: Path) -> None:
        # Re-review C1: a valid-id session must NOT be pulled into loop-mode by
        # another session's degraded global → inactive. The global is honored
        # only for an id-less (degraded) caller (test_active_on_legacy_global_when_idless).
        _claude_dir(tmp_path)
        (tmp_path / ".hm-loop-active").write_text("", encoding="utf-8")
        rc = worktree.main(
            ["loop-mode-active", str(tmp_path), "--claude-session-id", "deadbeefcafe"]
        )
        assert rc == 1

    def test_active_on_legacy_global_when_idless(self, tmp_path: Path) -> None:
        # An id-less (degraded) caller falls back to the global → active.
        _claude_dir(tmp_path)
        (tmp_path / ".hm-loop-active").write_text("", encoding="utf-8")
        rc = worktree.main(["loop-mode-active", str(tmp_path), "--claude-session-id", ""])
        assert rc == 0

    def test_empty_session_id_no_global_inactive(self, tmp_path: Path) -> None:
        claude = _claude_dir(tmp_path)
        (claude / ".hm-loop-execute-1").write_text(
            loop_marker.format_marker_content("aaaaaaaaaaaa", [tmp_path]), encoding="utf-8"
        )
        rc = worktree.main(["loop-mode-active", str(tmp_path), "--claude-session-id", ""])
        assert rc == 1

    def test_missing_base_is_usage_error(self) -> None:
        assert worktree.main(["loop-mode-active"]) == 2

    def test_trailing_flag_no_value_is_usage_error(self, tmp_path: Path) -> None:
        # re-review C2: a bare trailing --claude-session-id must NOT silently
        # degrade to inactive — it's a usage error.
        assert worktree.main(["loop-mode-active", str(tmp_path), "--claude-session-id"]) == 2


class TestWriteLoopMarkerContent:
    def test_writes_session_id_header(self, tmp_path: Path) -> None:
        wt = tmp_path / ".worktrees" / "execute-abc-1"
        wt.mkdir(parents=True)
        worktree._write_loop_marker(
            tmp_path, "execute-abc-1", [wt], claude_session_id="deadbeefcafe"
        )
        marker = tmp_path / ".claude" / ".hm-loop-execute-abc-1"
        text = marker.read_text(encoding="utf-8")
        assert loop_marker.parse_marker_session_id(text) == "deadbeefcafe"
        assert loop_marker.parse_marker_paths(text) == [str(wt)]

    def test_default_empty_session_id_back_compat(self, tmp_path: Path) -> None:
        wt = tmp_path / ".worktrees" / "execute-abc-1"
        wt.mkdir(parents=True)
        # No claude_session_id passed → header present but empty (legacy-ish).
        worktree._write_loop_marker(tmp_path, "execute-abc-1", [wt])
        marker = tmp_path / ".claude" / ".hm-loop-execute-abc-1"
        text = marker.read_text(encoding="utf-8")
        assert loop_marker.parse_marker_session_id(text) == ""
        assert loop_marker.parse_marker_paths(text) == [str(wt)]


class TestReadActiveWorktreesSkipsHeader:
    def test_header_excluded_real_dir_returned(self, tmp_path: Path) -> None:
        wt = tmp_path / ".worktrees" / "execute-abc-1"
        wt.mkdir(parents=True)
        worktree._write_loop_marker(
            tmp_path, "execute-abc-1", [wt], claude_session_id="deadbeefcafe"
        )
        active = worktree._read_active_worktrees(tmp_path)
        assert active == [wt]

    def test_header_dropped_by_prefix_not_existence(self, tmp_path: Path) -> None:
        # Hand-craft a marker whose header VALUE resolves to an existing path
        # to prove the parser drops it by the "/"-prefix rule, not by existence.
        claude = _claude_dir(tmp_path)
        wt = tmp_path / ".worktrees" / "execute-real"
        wt.mkdir(parents=True)
        # header line is "claude_session_id: <x>" → never starts with "/"
        (claude / ".hm-loop-execute-real").write_text(
            f"{loop_marker.MARKER_HEADER_KEY}: {wt}\n{wt}\n", encoding="utf-8"
        )
        active = worktree._read_active_worktrees(tmp_path)
        # exactly one entry (the path line), not duplicated by the header
        assert active == [wt]

    def test_legacy_pathonly_marker_still_read(self, tmp_path: Path) -> None:
        claude = _claude_dir(tmp_path)
        wt = tmp_path / ".worktrees" / "execute-legacy"
        wt.mkdir(parents=True)
        (claude / ".hm-loop-execute-legacy").write_text(f"{wt}\n", encoding="utf-8")
        assert worktree._read_active_worktrees(tmp_path) == [wt]


class TestOwnedUuidsFilenameUnchanged:
    def test_uuid_still_extracted_from_filename_not_content(self, tmp_path: Path) -> None:
        # ADR-005: the worktree session_uuid lives in the FILENAME; adding a
        # content header must not disturb _owned_session_uuids.
        wt = tmp_path / ".worktrees" / "execute-1234567890ab-20260101T0000Z"
        wt.mkdir(parents=True)
        worktree._write_loop_marker(
            tmp_path,
            "execute-1234567890ab-20260101T0000Z",
            [wt],
            claude_session_id="ffffffffffff",
        )
        owned = worktree._owned_session_uuids(tmp_path)
        assert "1234567890ab" in owned
        # the CONTENT claude_session_id must NOT leak into owned uuids
        assert "ffffffffffff" not in owned
