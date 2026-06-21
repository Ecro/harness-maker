"""loop_gate Stop-hook session-scoped matching (loop-marker-session-scoping P3)."""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.hooks import loop_gate
from harness_maker.loop_marker import format_marker_content


def _claude(base: Path) -> Path:
    d = base / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stop_payload(base: Path, session_id: str | None) -> str:
    payload: dict[str, object] = {
        "hook_event_name": "Stop",
        "cwd": str(base),
        "workspace": {"current_dir": str(base)},
    }
    if session_id is not None:
        payload["session_id"] = session_id
    return json.dumps(payload)


class TestStopHookSessionScoped:
    def test_own_session_marker_blocks(self, tmp_path: Path) -> None:
        claude = _claude(tmp_path)
        wt = tmp_path / ".worktrees" / "execute-1"
        wt.mkdir(parents=True)
        (claude / ".hm-loop-execute-1").write_text(
            format_marker_content("deadbeefcafe", [wt]), encoding="utf-8"
        )
        assert loop_gate._stop_hook(_stop_payload(tmp_path, "deadbeefcafe")) == 2

    def test_other_session_marker_allows(self, tmp_path: Path) -> None:
        # Session B is idle; only session A's marker exists → B must be free to stop.
        claude = _claude(tmp_path)
        wt = tmp_path / ".worktrees" / "execute-1"
        wt.mkdir(parents=True)
        (claude / ".hm-loop-execute-1").write_text(
            format_marker_content("aaaaaaaaaaaa", [wt]), encoding="utf-8"
        )
        assert loop_gate._stop_hook(_stop_payload(tmp_path, "bbbbbbbbbbbb")) == 0

    def test_no_marker_allows(self, tmp_path: Path) -> None:
        _claude(tmp_path)
        assert loop_gate._stop_hook(_stop_payload(tmp_path, "deadbeefcafe")) == 0

    def test_valid_id_session_ignores_foreign_global(self, tmp_path: Path) -> None:
        # Re-review C1 (supersedes first-review H2): a session WITH a valid
        # session_id must NOT be blocked by a session-blind global it did not
        # create — that would re-open cross-session interference for valid-id
        # sessions. It relies on content-match only; the global is honored solely
        # for id-less (degraded) sessions (test_absent_session_id_with_global_blocks).
        # Trade-off: a degraded loop whose Stop payload carries an id loses its own
        # global guard — accepted, since parallel-safety (never block a peer) > a
        # degraded loop self-guard. ADR-003.
        _claude(tmp_path)
        (tmp_path / ".hm-loop-active").write_text("", encoding="utf-8")
        assert loop_gate._stop_hook(_stop_payload(tmp_path, "deadbeefcafe")) == 0

    def test_stop_hook_active_guard_allows(self, tmp_path: Path) -> None:
        claude = _claude(tmp_path)
        (claude / ".hm-loop-execute-1").write_text(
            format_marker_content("deadbeefcafe", [tmp_path]), encoding="utf-8"
        )
        payload = json.loads(_stop_payload(tmp_path, "deadbeefcafe"))
        payload["stop_hook_active"] = True
        assert loop_gate._stop_hook(json.dumps(payload)) == 0

    def test_absent_session_id_no_global_allows(self, tmp_path: Path) -> None:
        # Degraded: payload has no session_id and there's no legacy global →
        # can't match → allow (ADR-003 absent-case, never a silent block).
        claude = _claude(tmp_path)
        wt = tmp_path / ".worktrees" / "execute-1"
        wt.mkdir(parents=True)
        (claude / ".hm-loop-execute-1").write_text(
            format_marker_content("aaaaaaaaaaaa", [wt]), encoding="utf-8"
        )
        assert loop_gate._stop_hook(_stop_payload(tmp_path, None)) == 0

    def test_absent_session_id_with_global_blocks(self, tmp_path: Path) -> None:
        _claude(tmp_path)
        (tmp_path / ".hm-loop-active").write_text("", encoding="utf-8")
        assert loop_gate._stop_hook(_stop_payload(tmp_path, None)) == 2

    def test_untame_session_id_matched_via_sanitize(self, tmp_path: Path) -> None:
        # Producer stored sanitized id; consumer must sanitize the payload too.
        claude = _claude(tmp_path)
        wt = tmp_path / ".worktrees" / "execute-1"
        wt.mkdir(parents=True)
        (claude / ".hm-loop-execute-1").write_text(
            format_marker_content("../weird", [wt]), encoding="utf-8"
        )
        assert loop_gate._stop_hook(_stop_payload(tmp_path, "../weird")) == 2
