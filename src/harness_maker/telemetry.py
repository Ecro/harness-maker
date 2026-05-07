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
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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
    # Resolve project root in priority order:
    #   1. stdin payload (Claude Code: workspace.current_dir; Cursor: cwd)
    #   2. env vars Cursor exposes for hook scripts (CURSOR_PROJECT_DIR is
    #      Cursor-native; CLAUDE_PROJECT_DIR is the compat alias)
    #   3. cwd of the spawning process — last resort, may be wrong if the
    #      IDE spawns the hook from $HOME or "/"
    cwd_str = (
        workspace.get("current_dir")
        or data.get("cwd")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CURSOR_PROJECT_DIR")
        or os.getcwd()
    )
    cwd = Path(cwd_str)
    metrics_path = cwd / ".claude" / "observability" / "metrics.jsonl"
    try:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        entry = _build_entry(data)
        with metrics_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"telemetry write failed: {e}", file=sys.stderr)
        return 0  # Never block Claude Code
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
