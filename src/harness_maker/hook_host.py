"""Tell a hook whether it is the `.claude/settings.json` copy running inside Cursor."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

# Prefixed onto every command in the rendered `.cursor/hooks.json`. Its presence in the
# hook's env says "I am the Cursor copy"; its presence in the file says the render is new
# enough for the Claude copy to stand down.
CURSOR_HOST_ENV = "HM_HOOK_HOST"
CURSOR_HOST_MARKER = f"{CURSOR_HOST_ENV}=cursor"


def is_claude_copy_in_cursor(payload: Mapping[str, object] | str) -> bool:
    """True when this process is the Claude-settings copy of a hook Cursor already runs.

    Cursor imports `.claude/settings.json` hooks ("Include Third-Party Plugins, Skills, and
    Other Configs", on by default) and runs every matching hook from every source with no
    dedupe, all with the same Cursor payload. With a cursor target that means each harness
    hook fires twice: two telemetry rows per tool call, and Claude-only hooks such as the
    `loop_gate` Stop hook running where `.cursor/hooks.json` deliberately left them out.

    `cursor_version` is in every payload Cursor sends and in none Claude Code sends, so a
    Claude Code session can never take this branch. The file check keeps an older
    `.cursor/hooks.json` (no marker) firing as before rather than leaving Cursor with none.
    Takes the parsed payload or the raw stdin text, whichever the hook already holds.
    """
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload) if payload.strip() else {}
        except ValueError:
            return False
        if not isinstance(parsed, dict):
            return False
        payload = parsed
    if "cursor_version" not in payload or os.environ.get(CURSOR_HOST_ENV) == "cursor":
        return False
    root = os.environ.get("CURSOR_PROJECT_DIR")
    roots = payload.get("workspace_roots")
    if not root and isinstance(roots, list) and roots and isinstance(roots[0], str):
        root = roots[0]
    root = root or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        text = (Path(root) / ".cursor" / "hooks.json").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return CURSOR_HOST_MARKER in text
