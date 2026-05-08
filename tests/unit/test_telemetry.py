"""Telemetry hook tests (per amendment §H)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from harness_maker import telemetry


def _run_main_with_stdin(monkeypatch: pytest.MonkeyPatch, stdin: str) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return telemetry.main()


def test_appends_jsonl_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "workspace": {"current_dir": str(tmp_path)},
        "tool_name": "Bash",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 20,
            "cache_read_input_tokens": 5,
        },
    }
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    metrics = tmp_path / ".claude" / "observability" / "metrics.jsonl"
    assert metrics.is_file()
    line = metrics.read_text().strip()
    entry = json.loads(line)
    assert entry["input_tokens"] == 10
    assert entry["output_tokens"] == 20
    assert entry["cache_read_tokens"] == 5
    assert entry["tool_name"] == "Bash"
    assert "timestamp" in entry


def test_creates_parent_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"workspace": {"current_dir": str(tmp_path)}}
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    assert (tmp_path / ".claude" / "observability").is_dir()


def test_malformed_stdin_does_not_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = _run_main_with_stdin(monkeypatch, "not json {{{")
    assert rc == 0
    metrics = tmp_path / ".claude" / "observability" / "metrics.jsonl"
    # Even on malformed input, we still write an empty entry
    assert metrics.is_file()


def test_empty_stdin_writes_default_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty stdin → no payload → event=unknown entry (still written so the
    file's existence remains a positive 'hook fired' signal). Token / tool
    fields are intentionally absent rather than zeroed — pre-0.5.4 wrote
    `input_tokens: 0` for everything which polluted cache_diagnostics."""
    monkeypatch.chdir(tmp_path)
    rc = _run_main_with_stdin(monkeypatch, "")
    assert rc == 0
    metrics = tmp_path / ".claude" / "observability" / "metrics.jsonl"
    assert metrics.is_file()
    entry = json.loads(metrics.read_text().strip())
    assert entry["event"] == "unknown"
    assert "timestamp" in entry
    assert "input_tokens" not in entry  # no fake-zero tokens


def test_cwd_falls_back_to_claude_project_dir_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When stdin lacks workspace.current_dir / cwd, CLAUDE_PROJECT_DIR
    env var (Cursor compat alias) wins over `os.getcwd()`. Without this,
    Cursor-spawned hooks may write to the wrong directory."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("CURSOR_PROJECT_DIR", raising=False)
    monkeypatch.chdir("/")  # ensure cwd is NOT tmp_path
    rc = _run_main_with_stdin(monkeypatch, "{}")
    assert rc == 0
    assert (tmp_path / ".claude" / "observability" / "metrics.jsonl").is_file()


def test_cwd_falls_back_to_cursor_project_dir_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CURSOR_PROJECT_DIR is the native Cursor env var; used when the
    stdin payload doesn't carry the cwd hint."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setenv("CURSOR_PROJECT_DIR", str(tmp_path))
    monkeypatch.chdir("/")
    rc = _run_main_with_stdin(monkeypatch, "{}")
    assert rc == 0
    assert (tmp_path / ".claude" / "observability" / "metrics.jsonl").is_file()


def test_empty_env_vars_fall_through_to_getcwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`CLAUDE_PROJECT_DIR=""` (empty string) is falsy → falls through to
    next fallback rather than writing to `/.claude/...`. Critical for
    not corrupting filesystem root when an env var is set but empty."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "")
    monkeypatch.setenv("CURSOR_PROJECT_DIR", "")
    monkeypatch.chdir(tmp_path)
    rc = _run_main_with_stdin(monkeypatch, "{}")
    assert rc == 0
    # Should land in tmp_path (via os.getcwd), NOT at root
    assert (tmp_path / ".claude" / "observability" / "metrics.jsonl").is_file()
    assert not Path("/.claude").exists()


def test_post_tool_use_payload_writes_token_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude Code-style payload (tool_name + usage) is tagged event=post_tool_use
    and carries token counts. This is what cache_diagnostics consumes."""
    payload = {
        "workspace": {"current_dir": str(tmp_path)},
        "tool_name": "Bash",
        "usage": {"input_tokens": 100, "cache_read_input_tokens": 80},
    }
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    entry = json.loads(
        (tmp_path / ".claude" / "observability" / "metrics.jsonl").read_text().strip(),
    )
    assert entry["event"] == "post_tool_use"
    assert entry["tool_name"] == "Bash"
    assert entry["input_tokens"] == 100
    assert entry["cache_read_tokens"] == 80
    assert "status" not in entry
    assert "loop_count" not in entry


def test_cursor_stop_payload_writes_per_turn_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cursor stop event (status + loop_count + duration_ms, no usage) is
    tagged event=stop and captures per-turn signals. cache_diagnostics
    filters these out so they don't pollute hit-rate calculation."""
    monkeypatch.setenv("CURSOR_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    payload = {
        "status": "completed",
        "loop_count": 3,
        "duration_ms": 12500,
        "model": "claude-opus-4-7",
        "conversation_id": "conv-abc",
    }
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    entry = json.loads(
        (tmp_path / ".claude" / "observability" / "metrics.jsonl").read_text().strip(),
    )
    assert entry["event"] == "stop"
    assert entry["status"] == "completed"
    assert entry["loop_count"] == 3
    assert entry["duration_ms"] == 12500
    assert entry["model"] == "claude-opus-4-7"
    assert entry["conversation_id"] == "conv-abc"
    # Token fields intentionally absent — Cursor never surfaces them
    assert "input_tokens" not in entry
    assert "cache_read_tokens" not in entry
    assert "tool_name" not in entry


def test_unknown_payload_writes_minimal_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Payload that's neither post_tool_use nor stop shape (e.g., a future
    Cursor session_start event we don't consume) gets event=unknown but
    still writes a timestamp — never silently drops."""
    monkeypatch.chdir(tmp_path)
    payload = {"some_future_field": "value"}
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    entry = json.loads(
        (tmp_path / ".claude" / "observability" / "metrics.jsonl").read_text().strip(),
    )
    assert entry["event"] == "unknown"
    assert "timestamp" in entry


# ── Phase 1: OTel-compatible fields + cost estimation ─────────────────────


def test_entry_has_span_id_and_trace_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "workspace": {"current_dir": str(tmp_path)},
        "tool_name": "Read",
        "usage": {"input_tokens": 100},
    }
    _run_main_with_stdin(monkeypatch, json.dumps(payload))
    entry = json.loads(
        (tmp_path / ".claude" / "observability" / "metrics.jsonl").read_text().strip(),
    )
    assert "span_id" in entry
    assert len(entry["span_id"]) == 16
    assert "trace_id" in entry
    assert len(entry["trace_id"]) > 0


def test_trace_id_uses_conversation_id_when_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "workspace": {"current_dir": str(tmp_path)},
        "tool_name": "Read",
        "usage": {"input_tokens": 100},
        "conversation_id": "conv-xyz-123",
    }
    _run_main_with_stdin(monkeypatch, json.dumps(payload))
    entry = json.loads(
        (tmp_path / ".claude" / "observability" / "metrics.jsonl").read_text().strip(),
    )
    assert entry["trace_id"] == "conv-xyz-123"


def test_cost_usd_present_for_post_tool_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "workspace": {"current_dir": str(tmp_path)},
        "tool_name": "Bash",
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_input_tokens": 200,
        },
    }
    _run_main_with_stdin(monkeypatch, json.dumps(payload))
    entry = json.loads(
        (tmp_path / ".claude" / "observability" / "metrics.jsonl").read_text().strip(),
    )
    assert "cost_usd" in entry
    assert entry["cost_usd"] > 0


def test_cost_usd_absent_for_stop_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CURSOR_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    payload = {"status": "completed", "duration_ms": 5000}
    _run_main_with_stdin(monkeypatch, json.dumps(payload))
    entry = json.loads(
        (tmp_path / ".claude" / "observability" / "metrics.jsonl").read_text().strip(),
    )
    assert "cost_usd" not in entry


def test_estimate_cost_function() -> None:
    from harness_maker.telemetry import _estimate_cost

    entry = {
        "input_tokens": 1_000_000,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
    }
    cost = _estimate_cost(entry, "sonnet")
    assert cost is not None
    assert abs(cost - 3.0) < 0.01  # $3/MTK input for sonnet

    assert _estimate_cost({}, "") is None
