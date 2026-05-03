"""PostToolUse telemetry hook — appends one JSONL line to .claude/observability/metrics.jsonl.

Per amendment §H. Hook input arrives via stdin as JSON; output is "ok" on stdout.
Must NEVER crash Claude Code: malformed input → empty entry, exit 0.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _build_entry(data: dict[str, Any]) -> dict[str, Any]:
    raw_usage = data.get("usage")
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "tool_name": data.get("tool_name"),
    }


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
    cwd_str = workspace.get("current_dir") or data.get("cwd") or os.getcwd()
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
