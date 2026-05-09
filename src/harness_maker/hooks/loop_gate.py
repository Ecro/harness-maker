"""Loop gate hook — prevents session termination while .hm-loop-active is set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _find_marker(start_dir: Path | None = None) -> Path | None:
    """Return path to .hm-loop-active if found in start_dir or any ancestor up to git root."""
    cwd = start_dir if start_dir is not None else Path.cwd()
    for directory in [cwd, *cwd.parents]:
        candidate = directory / ".hm-loop-active"
        if candidate.exists():
            return candidate
        if (directory / ".git").exists():
            break
    return None


def _stop_hook(stdin_text: str) -> int:
    """Stop hook mode: block session termination while loop is active.

    stop_hook_active guard MUST be checked first — omitting it causes an
    infinite Stop event loop because the hook fires again after exit 2.
    """
    try:
        data: object = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[loop-gate] warn: invalid JSON stdin: {e}\n")
        data = {}

    if isinstance(data, dict) and data.get("stop_hook_active"):
        return 0

    marker = _find_marker()
    if marker is None:
        return 0

    response = {
        "decision": "block",
        "reason": (
            f"/hm:loop is active ({marker}). "
            "To exit the loop early: rm .hm-loop-active"
        ),
    }
    print(json.dumps(response))
    return 2


def _pretooluse(stdin_text: str) -> int:  # noqa: ARG001
    """PreToolUse mode: advisory-only Cursor hook, always exits 0.

    Cursor has no Stop event equivalent. This hook injects a stderr reminder
    that the loop is active but never blocks tool use.
    """
    marker = _find_marker()
    if marker is not None:
        sys.stderr.write(
            f"[loop-gate] /hm:loop active ({marker}) — do not close this session.\n"
        )
    return 0


def main() -> None:
    """Entry point for python -m harness_maker.hooks.loop_gate."""
    parser = argparse.ArgumentParser(description="Loop gate hook")
    parser.add_argument(
        "--mode",
        choices=["stop-hook", "pretooluse"],
        required=True,
    )
    args = parser.parse_args()

    stdin_text = sys.stdin.read() if not sys.stdin.isatty() else ""

    if args.mode == "stop-hook":
        sys.exit(_stop_hook(stdin_text))
    else:
        sys.exit(_pretooluse(stdin_text))


if __name__ == "__main__":
    main()
