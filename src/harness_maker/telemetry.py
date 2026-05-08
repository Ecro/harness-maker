"""Hybrid telemetry hook — adapts to both Claude Code and Cursor IDE.

Per amendment §H. Hook input arrives via stdin as JSON; output is "ok" on stdout.
Must NEVER crash Claude Code or Cursor: malformed input → empty entry, exit 0.

Event shapes (PLAN-cursor-rootcause.md follow-up):

- **post_tool_use** (Claude Code PostToolUse): payload has `tool_name` + `usage`.
  We extract token counts for cache-diagnostic Layer 3.
- **stop** (Cursor stop): payload has `status` / `loop_count` / `duration_ms` but
  NO `usage` (Cursor does not surface tokens in any hook event — confirmed by
  Cursor team in <https://forum.cursor.com/t/cursordiskkv-table-records-always-show-0-for-tokencount/155984>).
  We capture per-turn signals; cache_diagnostics filters these out so they
  don't pollute hit-rate calculation.
- **unknown**: minimal entry (timestamp + event hint) — never silently skip.

Each entry carries an `event` field so downstream readers can filter cleanly.
Older entries (pre-0.5.4) lacked this field; cache_diagnostics treats absent
`event` as `post_tool_use` for backward compatibility.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

COST_PER_MTK: dict[str, dict[str, float]] = {
    "opus": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
    "sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
    "haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.025, "cache_write": 0.3},
}
_DEFAULT_COST = COST_PER_MTK["sonnet"]

# ADR-107 (0.7.1): persist only the tool_input keys that scan_sequence /
# prod_name_guard inspect. Foreign fields are dropped — minimises secret-
# leak surface and keeps the persisted line size bounded.
_ALLOWED_TOOL_INPUT_KEYS: frozenset[str] = frozenset(
    {"path", "file_path", "command", "target", "database", "url", "query"}
)
_VALUE_CAP = 256

# ADR-107 secret-pattern redaction. Applied per string value BEFORE the
# 256-char cap so a partial-token tail can never survive truncation.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),  # Anthropic / OpenAI keys
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub personal access tokens
    re.compile(r"AKIA[A-Z0-9]{16,}"),  # AWS access keys
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),  # OAuth Bearer
)


def _redact_value(s: str) -> str:
    """Apply known-secret-pattern redaction; keep value otherwise unchanged."""
    for pattern in _SECRET_PATTERNS:
        s = pattern.sub("[REDACTED]", s)
    return s


def _project_tool_input(raw: dict[str, Any]) -> dict[str, Any]:
    """Whitelist-project tool_input → safe, capped, secret-redacted dict.

    Prevents both schema bloat (foreign keys with potentially-sensitive
    values) and partial-secret leaks via end-of-buffer truncation. Each
    string value is redacted FIRST, then capped at 256 chars; non-string
    primitives (int/bool/null) pass through unchanged.
    """
    safe: dict[str, Any] = {}
    for key in _ALLOWED_TOOL_INPUT_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, str):
            redacted = _redact_value(value)
            if len(redacted) > _VALUE_CAP:
                redacted = redacted[:_VALUE_CAP] + "...<truncated>"
            safe[key] = redacted
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key] = value
        # Drop non-primitive nested values (lists/dicts) — scan_sequence
        # only consults primitive values via _extract_target.
    return safe


def _estimate_cost(entry: dict[str, Any], model: str = "") -> float | None:
    """Estimate USD cost from token counts. Returns None if no token data."""
    inp = entry.get("input_tokens", 0) or 0
    out = entry.get("output_tokens", 0) or 0
    cache_read = entry.get("cache_read_tokens", 0) or 0
    cache_write = entry.get("cache_creation_tokens", 0) or 0
    if inp == 0 and out == 0 and cache_read == 0 and cache_write == 0:
        return None
    m = model.lower()
    rates = _DEFAULT_COST
    for key, val in COST_PER_MTK.items():
        if key in m:
            rates = val
            break
    return (
        inp * rates["input"]
        + out * rates["output"]
        + cache_read * rates["cache_read"]
        + cache_write * rates["cache_write"]
    ) / 1_000_000


def _detect_event(data: dict[str, Any]) -> str:
    """Classify payload shape into a known event type.

    Order matters: tool_name is the strongest signal (post_tool_use carries
    it on both IDEs). status/loop_count are unique to Cursor's stop event.
    Anything else (e.g. session_start with no useful fields) → unknown.
    """
    if "tool_name" in data:
        return "post_tool_use"
    if "status" in data or "loop_count" in data or "duration_ms" in data:
        return "stop"
    return "unknown"


def _build_entry(data: dict[str, Any]) -> dict[str, Any]:
    """Adapt the stdin payload to a JSONL entry tagged by event type."""
    event = _detect_event(data)
    entry: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "span_id": uuid.uuid4().hex[:16],
        "trace_id": data.get("conversation_id") or uuid.uuid4().hex,
        "event": event,
    }
    if event == "post_tool_use":
        raw_usage = data.get("usage")
        usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
        entry["tool_name"] = data.get("tool_name")
        entry["input_tokens"] = usage.get("input_tokens", 0)
        entry["output_tokens"] = usage.get("output_tokens", 0)
        entry["cache_read_tokens"] = usage.get("cache_read_input_tokens", 0)
        entry["cache_creation_tokens"] = usage.get("cache_creation_input_tokens", 0)
        cost = _estimate_cost(entry, data.get("model", ""))
        if cost is not None:
            entry["cost_usd"] = round(cost, 6)
        # 0.7.1 (ADR-107): whitelist-project tool_input → known-good keys
        # with value-level secret redaction + 256-char cap. Replaces the
        # earlier 2 KiB string-slice that produced invalid JSON on overflow
        # and could preserve partial-secret tails.
        raw_input = data.get("tool_input")
        if isinstance(raw_input, dict):
            safe_input = _project_tool_input(raw_input)
            if safe_input:
                # Persist as a JSON string so the on-disk schema stays
                # compatible with pre-0.7.1 consumers reading `tool_input`.
                entry["tool_input"] = json.dumps(safe_input, ensure_ascii=False)
    elif event == "stop":
        # Cursor stop fires once per agent turn — meaningful per-turn signal
        # even though tokens aren't available. status/loop_count/duration_ms
        # power custom dashboards; conversation_id allows cross-session join.
        entry["status"] = data.get("status")
        entry["loop_count"] = data.get("loop_count")
        entry["duration_ms"] = data.get("duration_ms")
        entry["model"] = data.get("model")
        entry["conversation_id"] = data.get("conversation_id")
    return entry


def main() -> int:
    raw = ""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        raw = ""
    data: dict[str, Any] = {}
    if raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                data = parsed
        except (json.JSONDecodeError, ValueError):
            data = {}
    raw_workspace = data.get("workspace")
    workspace: dict[str, Any] = raw_workspace if isinstance(raw_workspace, dict) else {}
    # Resolve project root via env-var-first chain (ADR-102, 0.7.1):
    #   1. CLAUDE_PROJECT_DIR — Claude Code-native, set per-session
    #   2. CURSOR_PROJECT_DIR — Cursor-native equivalent
    #   3. workspace.current_dir from stdin (Claude Code's typed payload —
    #      shape is well-defined, unlike the bare `cwd` key which a poisoned
    #      tool result could spoof)
    #   4. os.getcwd() — last-resort fallback; may be $HOME or / if the IDE
    #      spawns the hook from outside the project
    # The bare stdin `cwd` field is intentionally NOT consulted: prior to
    # 0.7.1 it was a path-traversal primitive (a poisoned PostToolUse
    # payload could redirect metrics writes to an attacker-chosen path).
    cwd_str = (
        os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CURSOR_PROJECT_DIR")
        or workspace.get("current_dir")
        or os.getcwd()
    )
    cwd = Path(cwd_str)
    # ADR-103 (0.7.1): rotate per-day so a long-lived session does not
    # accumulate an unbounded single file. Readers (security_scanner,
    # cache_diagnostics) walk dated files newest-first via _metrics_io
    # and fall back to the legacy `metrics.jsonl` for pre-0.7.1 entries.
    obs_dir = cwd / ".claude" / "observability"
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    metrics_path = obs_dir / f"metrics-{today}.jsonl"
    try:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        entry = _build_entry(data)
        # Atomic append: O_APPEND + a single os.write() syscall guarantees
        # POSIX atomicity for writes ≤ PIPE_BUF (4096 bytes). One JSONL entry
        # is ~200–400 bytes, well within the bound. The buffered TextIOWrapper
        # returned by ``Path.open("a")`` could split a write across multiple
        # syscalls and let two concurrent hooks interleave their lines; using
        # raw os.write() bypasses Python's buffer.
        line = (json.dumps(entry) + "\n").encode("utf-8")
        fd = os.open(
            str(metrics_path),
            os.O_WRONLY | os.O_APPEND | os.O_CREAT,
            0o644,
        )
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except OSError as e:
        print(f"telemetry write failed: {e}", file=sys.stderr)
        return 0  # Never block Claude Code
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
