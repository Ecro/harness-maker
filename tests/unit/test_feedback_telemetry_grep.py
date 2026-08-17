"""Phase 2 — telemetry_grep bounded readers.

PLAN-auto-feedback-2026-05 Phase 2 exit criterion (a)-(e):
(a) hook-error stop event detection
(b) silent-intent-miss row inclusion
(c) build-break review row inclusion
(d) clean-session empty return
(e) ≤2KB output bound enforced at runtime
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker.feedback.telemetry_grep import (
    TELEMETRY_GREP_MAX_BYTES,
    gather_recent_signals,
    last_stop_with_trace,
)


def _today_metrics_file(obs_dir: Path) -> Path:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    obs_dir.mkdir(parents=True, exist_ok=True)
    return obs_dir / f"metrics-{today}.jsonl"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


# ── last_stop_with_trace ─────────────────────────────────────────────────────


def test_last_stop_with_trace_clean_session_returns_empty(tmp_path: Path) -> None:
    """(d) No telemetry dir → empty string. No exception."""
    assert last_stop_with_trace(tmp_path / "nope") == ""


def test_last_stop_with_trace_empty_dir_returns_empty(tmp_path: Path) -> None:
    """(d) Dir exists but no metrics-*.jsonl → empty string."""
    (tmp_path / ".claude/observability").mkdir(parents=True)
    assert last_stop_with_trace(tmp_path / ".claude/observability") == ""


def test_last_stop_with_trace_finds_stop_and_joins_tool_uses(tmp_path: Path) -> None:
    """(a) stop event + matching post_tool_use rows by trace_id are returned together."""
    obs = tmp_path / ".claude/observability"
    f = _today_metrics_file(obs)
    _write_jsonl(
        f,
        [
            {"event": "post_tool_use", "trace_id": "trace-A", "tool_name": "Read"},
            {
                "event": "post_tool_use",
                "trace_id": "trace-A",
                "tool_name": "Bash",
                "duration_ms": 12345,
            },
            {
                "event": "post_tool_use",
                "trace_id": "trace-B",
                "tool_name": "Edit",
            },  # different trace
            {"event": "stop", "trace_id": "trace-A", "status": "failed", "duration_ms": 18000},
        ],
    )
    out = last_stop_with_trace(obs)
    parsed = json.loads(out)
    assert parsed["stop"]["trace_id"] == "trace-A"
    assert parsed["stop"]["status"] == "failed"
    # Only same-trace tool_uses included; trace-B excluded.
    trace_ids = {r["trace_id"] for r in parsed["tool_uses"]}
    assert trace_ids == {"trace-A"}


def test_last_stop_with_trace_no_stop_event_returns_empty(tmp_path: Path) -> None:
    """(d) tool_uses without any stop event → empty string (no draft trigger)."""
    obs = tmp_path / ".claude/observability"
    f = _today_metrics_file(obs)
    _write_jsonl(
        f,
        [{"event": "post_tool_use", "trace_id": "trace-A", "tool_name": "Read"}],
    )
    assert last_stop_with_trace(obs) == ""


def test_last_stop_with_trace_respects_byte_cap(tmp_path: Path) -> None:
    """(e) Huge fixture → output ≤ TELEMETRY_GREP_MAX_BYTES, truncation marker present."""
    obs = tmp_path / ".claude/observability"
    f = _today_metrics_file(obs)
    huge_args = "x" * 4000
    rows: list[dict[str, Any]] = [
        {"event": "post_tool_use", "trace_id": "T", "tool_input": huge_args, "i": i}
        for i in range(50)
    ]
    rows.append({"event": "stop", "trace_id": "T", "status": "failed"})
    _write_jsonl(f, rows)
    out = last_stop_with_trace(obs)
    assert len(out) <= TELEMETRY_GREP_MAX_BYTES
    assert "...<truncated>" in out


def test_last_stop_with_trace_malformed_jsonl_silently_skipped(tmp_path: Path) -> None:
    """Malformed lines do not crash the reader (telemetry is best-effort)."""
    obs = tmp_path / ".claude/observability"
    f = _today_metrics_file(obs)
    f.write_text(
        "{not valid json\n" + json.dumps({"event": "stop", "trace_id": "T", "status": "ok"}) + "\n",
        encoding="utf-8",
    )
    out = last_stop_with_trace(obs)
    parsed = json.loads(out)
    assert parsed["stop"]["trace_id"] == "T"


# ── gather_recent_signals ────────────────────────────────────────────────────


def test_gather_clean_session_returns_three_empty_buckets(tmp_path: Path) -> None:
    """(d) No telemetry → bundle has all 3 keys with empty/falsy values, no crash."""
    out = gather_recent_signals(tmp_path / ".claude/observability")
    parsed = json.loads(out)
    assert parsed == {"metrics": "", "silent_intent_miss": [], "build_break": []}


def test_gather_picks_up_silent_intent_miss_rows(tmp_path: Path) -> None:
    """(b) silent-intent-miss-{slug}.jsonl rows are bundled in newest-first order."""
    obs = tmp_path / ".claude/observability"
    f = obs / "silent-intent-miss-foo.jsonl"
    _write_jsonl(
        f,
        [
            {"slot": "preset", "trigger": "review-mismatch", "ts": "2026-05-22T10:00:00Z"},
            {"slot": "dev_mode", "trigger": "review-mismatch", "ts": "2026-05-22T11:00:00Z"},
        ],
    )
    out = gather_recent_signals(obs)
    parsed = json.loads(out)
    assert len(parsed["silent_intent_miss"]) == 2
    # Newest-first.
    assert parsed["silent_intent_miss"][0]["slot"] == "dev_mode"


def test_gather_picks_up_build_break_review_rows(tmp_path: Path) -> None:
    """(c) review-{date}.jsonl rows with build_break_count>0 are included."""
    obs = tmp_path / ".claude/observability"
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    rf = obs / f"review-{today}.jsonl"
    _write_jsonl(
        rf,
        [
            {"slug": "x", "round": 1, "build_break_count": 0, "auto_fix_reverted_n": 0},
            {"slug": "x", "round": 2, "build_break_count": 2, "auto_fix_reverted_n": 1},
        ],
    )
    out = gather_recent_signals(obs)
    parsed = json.loads(out)
    assert len(parsed["build_break"]) == 1
    assert parsed["build_break"][0]["round"] == 2


def test_gather_respects_byte_cap(tmp_path: Path) -> None:
    """(e) Huge fixtures across all 3 sources still cap to TELEMETRY_GREP_MAX_BYTES."""
    obs = tmp_path / ".claude/observability"
    big = "z" * 1000
    f = _today_metrics_file(obs)
    _write_jsonl(
        f,
        [{"event": "post_tool_use", "trace_id": "T", "data": big, "i": i} for i in range(10)]
        + [{"event": "stop", "trace_id": "T", "data": big}],
    )
    sim = obs / "silent-intent-miss-x.jsonl"
    _write_jsonl(sim, [{"slot": big, "i": i} for i in range(10)])
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    rev = obs / f"review-{today}.jsonl"
    _write_jsonl(rev, [{"slug": big, "round": i, "build_break_count": 1} for i in range(5)])
    out = gather_recent_signals(obs)
    assert len(out) <= TELEMETRY_GREP_MAX_BYTES
    # Truncation marker present (output overflowed at least one bucket).
    assert re.search(r"\.\.\.<truncated>", out)
