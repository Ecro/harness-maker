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


def _read_today_entries(tmp_path: Path) -> list[dict]:
    """Read all entries telemetry wrote today (handles 0.7.1 dated filenames)."""
    obs_dir = tmp_path / ".claude" / "observability"
    if not obs_dir.is_dir():
        return []
    entries = []
    for f in sorted(obs_dir.glob("metrics-*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
    return entries


def _read_today_text(tmp_path: Path) -> str:
    """Concatenate all today's metric file text — convenience for tests
    that previously read a single ``metrics.jsonl`` file."""
    obs_dir = tmp_path / ".claude" / "observability"
    parts: list[str] = []
    for f in sorted(obs_dir.glob("metrics-*.jsonl")):
        parts.append(f.read_text(encoding="utf-8"))
    return "".join(parts)


def _metrics_file(tmp_path: Path) -> Path:
    """Return the (single) dated metrics file written by telemetry today.

    Tests in this suite produce exactly one entry per ``main()`` invocation,
    so a single dated file always exists. If multiple files are present
    (rare — only when the test crosses midnight), returns the most recent.
    """
    obs_dir = tmp_path / ".claude" / "observability"
    files = sorted(obs_dir.glob("metrics-*.jsonl"))
    if not files:
        # Fall back to the legacy filename so the FileNotFoundError raised
        # by callers still pinpoints the missing path.
        return obs_dir / "metrics.jsonl"
    return files[-1]


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
    metrics = _metrics_file(tmp_path)
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
    metrics = _metrics_file(tmp_path)
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
    metrics = _metrics_file(tmp_path)
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
    assert (_metrics_file(tmp_path)).is_file()


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
    assert (_metrics_file(tmp_path)).is_file()


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
    assert (_metrics_file(tmp_path)).is_file()
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
        (_metrics_file(tmp_path)).read_text().strip(),
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
        (_metrics_file(tmp_path)).read_text().strip(),
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
        (_metrics_file(tmp_path)).read_text().strip(),
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
        (_metrics_file(tmp_path)).read_text().strip(),
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
        (_metrics_file(tmp_path)).read_text().strip(),
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
        (_metrics_file(tmp_path)).read_text().strip(),
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
        (_metrics_file(tmp_path)).read_text().strip(),
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


# 0.7.1 ADR-102: stdin `cwd` field is now ignored entirely (path-traversal fix).
def test_cwd_precedence_ignores_stdin_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A poisoned ``{"cwd": "/etc"}`` in stdin must NOT redirect the metrics
    write target. ADR-102: only env vars + workspace.current_dir + os.getcwd
    are consulted; the bare stdin `cwd` key is dropped from the chain."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("CURSOR_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    payload = {"cwd": "/etc", "tool_name": "Bash"}  # adversarial cwd
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    # Telemetry must have written under tmp_path (via os.getcwd), NEVER /etc.
    assert (_metrics_file(tmp_path)).is_file()
    assert not Path("/etc/.claude").exists()


# 0.7.1 ADR-107: tool_input is whitelist-projected, not raw-truncated.
def test_tool_input_whitelist_drops_unknown_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Foreign keys in tool_input are dropped on write — defends against
    schema bloat and incidental secret leaks via unknown fields."""
    payload = {
        "workspace": {"current_dir": str(tmp_path)},
        "tool_name": "Read",
        "tool_input": {
            "path": "/data/regular.json",
            "extra_secret": "sk-ABCDEFGHIJ12345678",  # not in whitelist → dropped
        },
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    entry = json.loads((_metrics_file(tmp_path)).read_text().strip())
    persisted = json.loads(entry["tool_input"])
    assert persisted == {"path": "/data/regular.json"}
    assert "extra_secret" not in persisted


# 0.7.1 ADR-107 secret-pattern redaction.
def test_tool_input_redacts_known_secret_patterns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Known-secret regex (sk-/ghp_/AKIA/Bearer) → [REDACTED] before the
    256-char cap, so a partial-secret tail can never survive truncation."""
    payload = {
        "workspace": {"current_dir": str(tmp_path)},
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                "curl -H 'Authorization: Bearer sk-prod-abc123def456ghi789' https://api.example.com"
            ),
        },
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    entry = json.loads((_metrics_file(tmp_path)).read_text().strip())
    persisted = json.loads(entry["tool_input"])
    cmd = persisted["command"]
    # The literal secret bytes must NOT appear in the persisted command.
    assert "sk-prod-abc" not in cmd
    assert "[REDACTED]" in cmd


# ── Phase 9: harness_yaml_override capture (ADR-005, validator C3/W8) ─────


def _overrides_jsonl(tmp_path: Path) -> Path:
    return tmp_path / ".claude" / "observability" / "adaptive" / "overrides.jsonl"


def test_override_record_extra_forbid() -> None:
    """OverrideRecord rejects unknown fields — guards against schema drift
    between Phase 9 emitter and Phase 10 reader (validator C3)."""
    import pytest
    from pydantic import ValidationError

    from harness_maker.telemetry import OverrideRecord

    with pytest.raises(ValidationError):
        OverrideRecord(
            ts="2026-05-16T12:00:00+00:00",
            axis_path="preset",
            before="Side",
            after="Production",
            source="configure-exit",
            future_field="oops",  # type: ignore[call-arg]
        )


def test_override_record_required_fields() -> None:
    """ts / axis_path / source are required; schema_version defaults to 1."""
    import pytest
    from pydantic import ValidationError

    from harness_maker.telemetry import SCHEMA_VERSION, OverrideRecord

    record = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="Side",
        after="Production",
        source="configure-exit",
    )
    assert record.schema_version == SCHEMA_VERSION
    # Missing required field raises
    with pytest.raises(ValidationError):
        OverrideRecord(ts="x", axis_path="y")  # type: ignore[call-arg]


def test_emit_override_writes_jsonl(tmp_path: Path) -> None:
    from harness_maker.telemetry import OverrideRecord, emit_override

    record = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="Side",
        after="Production",
        source="configure-exit",
    )
    emit_override(record, tmp_path)
    path = _overrides_jsonl(tmp_path)
    assert path.is_file()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["axis_path"] == "preset"
    assert data["before"] == "Side"
    assert data["after"] == "Production"
    assert data["source"] == "configure-exit"
    assert data["schema_version"] == 1


def test_emit_override_disable_telemetry_is_noop(tmp_path: Path) -> None:
    """ADR-005: opt-out short-circuits before any disk write."""
    from harness_maker.telemetry import OverrideRecord, emit_override

    record = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="Side",
        after="Production",
        source="configure-exit",
    )
    emit_override(record, tmp_path, disable_telemetry=True)
    assert not _overrides_jsonl(tmp_path).exists()


def test_emit_override_dedup(tmp_path: Path) -> None:
    """Same logical event (matching ts + axis_path + after) records once,
    even if both capture sites observe it (validator W8)."""
    from harness_maker.telemetry import OverrideRecord, emit_override

    record_primary = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="Side",
        after="Production",
        source="configure-exit",
    )
    record_secondary = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="Side",
        after="Production",
        source="session-start",
    )
    emit_override(record_primary, tmp_path)
    emit_override(record_secondary, tmp_path)
    lines = _overrides_jsonl(tmp_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["source"] == "configure-exit"


def test_emit_override_appends_distinct_records(tmp_path: Path) -> None:
    """Distinct ts → distinct record. Verifies dedup is not over-broad."""
    from harness_maker.telemetry import OverrideRecord, emit_override

    rec1 = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="Side",
        after="Production",
        source="configure-exit",
    )
    rec2 = OverrideRecord(
        ts="2026-05-16T13:00:00+00:00",
        axis_path="preset",
        before="Production",
        after="Side",
        source="configure-exit",
    )
    emit_override(rec1, tmp_path)
    emit_override(rec2, tmp_path)
    lines = _overrides_jsonl(tmp_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_dedup_key_stable() -> None:
    from harness_maker.telemetry import OverrideRecord, _dedup_key

    a = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="Side",
        after="Production",
        source="configure-exit",
    )
    b = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="ignored",
        after="Production",
        source="session-start",
        reason="post-hoc",
    )
    # Same ts + axis + after → identical key (before/source/reason ignored).
    assert _dedup_key(a) == _dedup_key(b)


def test_load_overrides_filters_schema_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown schema_version lines are skipped with a warning (validator C3)."""
    from harness_maker.telemetry import load_overrides

    path = _overrides_jsonl(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    valid = {
        "schema_version": 1,
        "ts": "2026-05-16T12:00:00+00:00",
        "axis_path": "preset",
        "before": "Side",
        "after": "Production",
        "source": "configure-exit",
        "reason": "",
    }
    future = {
        "schema_version": 99,
        "ts": "2026-05-16T13:00:00+00:00",
        "axis_path": "preset",
        "before": "Side",
        "after": "Production",
        "source": "configure-exit",
        "reason": "",
    }
    path.write_text(json.dumps(valid) + "\n" + json.dumps(future) + "\n", encoding="utf-8")
    records = load_overrides(tmp_path)
    assert len(records) == 1
    assert records[0].schema_version == 1


def test_load_overrides_missing_file_returns_empty(tmp_path: Path) -> None:
    from harness_maker.telemetry import load_overrides

    assert load_overrides(tmp_path) == []


def test_load_overrides_skips_corrupt_lines(tmp_path: Path) -> None:
    """Telemetry reader must NEVER block Phase 10 on corrupt jsonl —
    one bad line cannot starve the audit."""
    from harness_maker.telemetry import load_overrides

    path = _overrides_jsonl(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    valid = {
        "schema_version": 1,
        "ts": "2026-05-16T12:00:00+00:00",
        "axis_path": "preset",
        "before": "Side",
        "after": "Production",
        "source": "configure-exit",
        "reason": "",
    }
    path.write_text(
        "not json {{{\n" + json.dumps(valid) + "\n" + "{}\n",
        encoding="utf-8",
    )
    records = load_overrides(tmp_path)
    assert len(records) == 1


def test_compute_yaml_diff_leaf_change() -> None:
    from harness_maker.telemetry import compute_yaml_diff

    records = compute_yaml_diff(
        {"preset": "Side"},
        {"preset": "Production"},
        ts="2026-05-16T12:00:00+00:00",
    )
    assert len(records) == 1
    assert records[0].axis_path == "preset"
    assert records[0].before == "Side"
    assert records[0].after == "Production"
    assert records[0].schema_version == 1


def test_compute_yaml_diff_nested() -> None:
    from harness_maker.telemetry import compute_yaml_diff

    records = compute_yaml_diff(
        {"second_brain": {"enabled": False, "vault_path": ""}},
        {"second_brain": {"enabled": True, "vault_path": "/tmp/v"}},
        ts="2026-05-16T12:00:00+00:00",
    )
    paths = sorted(r.axis_path for r in records)
    assert paths == ["second_brain.enabled", "second_brain.vault_path"]


def test_compute_yaml_diff_skips_identical() -> None:
    from harness_maker.telemetry import compute_yaml_diff

    records = compute_yaml_diff(
        {"preset": "Side", "locale": "en"},
        {"preset": "Side", "locale": "en"},
        ts="2026-05-16T12:00:00+00:00",
    )
    assert records == []


def test_compute_yaml_diff_skips_private_keys() -> None:
    """Underscore-prefixed keys are reserved for telemetry breadcrumbs
    and must NEVER bubble up as user-driven overrides."""
    from harness_maker.telemetry import compute_yaml_diff

    records = compute_yaml_diff(
        {"_internal": "old", "preset": "Side"},
        {"_internal": "new", "preset": "Production"},
        ts="2026-05-16T12:00:00+00:00",
    )
    assert len(records) == 1
    assert records[0].axis_path == "preset"


def test_compute_yaml_diff_records_carry_schema_version() -> None:
    """Validator C3 invariant: every emitted record has schema_version."""
    from harness_maker.telemetry import SCHEMA_VERSION, compute_yaml_diff

    records = compute_yaml_diff(
        {"a": 1, "b": {"c": 2}},
        {"a": 99, "b": {"c": 100}},
        ts="2026-05-16T12:00:00+00:00",
    )
    assert all(r.schema_version == SCHEMA_VERSION for r in records)


def test_emit_override_persists_schema_version_on_disk(tmp_path: Path) -> None:
    """On-disk JSONL line must carry schema_version so Phase 10 reader
    can filter (validator C3)."""
    from harness_maker.telemetry import OverrideRecord, emit_override

    record = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="Side",
        after="Production",
        source="configure-exit",
    )
    emit_override(record, tmp_path)
    line = _overrides_jsonl(tmp_path).read_text(encoding="utf-8").strip()
    assert json.loads(line)["schema_version"] == 1
