"""Unit tests for the SessionStart env-file hook (loop-marker-session-scoping P1)."""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.hooks import sessionid_envfile


def _payload(session_id: str) -> str:
    return json.dumps({"hook_event_name": "SessionStart", "session_id": session_id})


class TestSessionIdEnvFile:
    def test_writes_hm_session_id_line(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        rc = sessionid_envfile.run(_payload("0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9"), env_file)
        assert rc == 0
        content = env_file.read_text(encoding="utf-8")
        assert "HM_SESSION_ID=0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9" in content

    def test_sanitizes_untame_id(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        sessionid_envfile.run(_payload("../../evil"), env_file)
        content = env_file.read_text(encoding="utf-8")
        assert "../../evil" not in content
        assert "HM_SESSION_ID=" in content

    def test_idempotent_on_resume_overwrites_not_appends(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        sessionid_envfile.run(_payload("deadbeefcafe1"), env_file)
        sessionid_envfile.run(_payload("feedfacefeed2"), env_file)
        content = env_file.read_text(encoding="utf-8")
        # exactly one HM_SESSION_ID line, carrying the latest value
        assert content.count("HM_SESSION_ID=") == 1
        assert "HM_SESSION_ID=feedfacefeed2" in content

    def test_preserves_other_env_lines(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("EXISTING=keepme\n", encoding="utf-8")
        sessionid_envfile.run(_payload("deadbeefcafe1"), env_file)
        content = env_file.read_text(encoding="utf-8")
        assert "EXISTING=keepme" in content
        assert "HM_SESSION_ID=deadbeefcafe1" in content

    def test_missing_env_file_path_is_noop_exit0(self) -> None:
        # CLAUDE_ENV_FILE unset → degraded (ADR-003), never block session start
        assert sessionid_envfile.run(_payload("deadbeefcafe1"), None) == 0

    def test_bad_json_is_noop_exit0(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        assert sessionid_envfile.run("{not json", env_file) == 0
        assert not env_file.exists()

    def test_absent_session_id_is_noop_exit0(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        assert sessionid_envfile.run(json.dumps({"hook_event_name": "SessionStart"}), env_file) == 0
        assert not env_file.exists()

    def test_empty_session_id_is_noop(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        assert sessionid_envfile.run(_payload(""), env_file) == 0
        assert not env_file.exists()
