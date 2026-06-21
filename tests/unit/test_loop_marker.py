"""Unit tests for the shared loop-marker content helpers (loop-marker-session-scoping)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from harness_maker import loop_marker


class TestSanitizeSessionId:
    def test_uuid_passes_through_verbatim(self) -> None:
        sid = "0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9"
        assert loop_marker.sanitize_session_id(sid) == sid

    def test_hex_passes_through_verbatim(self) -> None:
        sid = "366992255376abcd"
        assert loop_marker.sanitize_session_id(sid) == sid

    def test_non_tame_is_hashed(self) -> None:
        sid = "../../etc/passwd"
        out = loop_marker.sanitize_session_id(sid)
        assert out == hashlib.sha256(sid.encode("utf-8")).hexdigest()[:16]
        assert "/" not in out

    def test_empty_returns_empty(self) -> None:
        assert loop_marker.sanitize_session_id("") == ""

    def test_too_short_is_hashed(self) -> None:
        # below the 8-char floor of the allowlist → hashed, never verbatim
        assert loop_marker.sanitize_session_id("abc") != "abc"


class TestMarkerContentRoundTrip:
    def test_format_then_parse_session_id(self) -> None:
        text = loop_marker.format_marker_content("deadbeefcafe", [Path("/a/b"), Path("/c/d")])
        assert loop_marker.parse_marker_session_id(text) == "deadbeefcafe"

    def test_format_then_parse_paths(self) -> None:
        text = loop_marker.format_marker_content("deadbeefcafe", [Path("/a/b"), Path("/c/d")])
        assert loop_marker.parse_marker_paths(text) == ["/a/b", "/c/d"]

    def test_header_dropped_by_prefix_not_existence(self) -> None:
        # The header value, even if it happened to look path-ish, must be
        # excluded by the startswith("/") rule — never treated as a worktree
        # path (validator W1: prefix-not-existence).
        text = loop_marker.format_marker_content("deadbeefcafe", [Path("/real/wt")])
        paths = loop_marker.parse_marker_paths(text)
        assert paths == ["/real/wt"]
        assert all(p.startswith("/") for p in paths)
        assert "deadbeefcafe" not in "".join(paths)

    def test_no_isolation_marker_has_empty_paths(self) -> None:
        text = loop_marker.format_marker_content("deadbeefcafe", [])
        assert loop_marker.parse_marker_session_id(text) == "deadbeefcafe"
        assert loop_marker.parse_marker_paths(text) == []

    def test_empty_session_id_header_parses_to_empty(self) -> None:
        text = loop_marker.format_marker_content("", [Path("/a/b")])
        assert loop_marker.parse_marker_session_id(text) == ""
        assert loop_marker.parse_marker_paths(text) == ["/a/b"]

    def test_legacy_pathonly_marker_parses(self) -> None:
        # A pre-upgrade marker (no header) must still yield its paths and an
        # empty session id (back-compat).
        legacy = "/a/b\n/c/d\n"
        assert loop_marker.parse_marker_session_id(legacy) == ""
        assert loop_marker.parse_marker_paths(legacy) == ["/a/b", "/c/d"]

    def test_session_id_in_content_is_sanitized(self) -> None:
        text = loop_marker.format_marker_content("../evil", [Path("/a")])
        # the stored header is the sanitized form, never the raw value
        assert "../evil" not in text
        assert loop_marker.parse_marker_session_id(text) == loop_marker.sanitize_session_id(
            "../evil"
        )
