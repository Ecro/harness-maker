"""permission_gate hook — block Bash invocations that match dangerous patterns.

Why: secscan.hook_injection already curates the canonical list of unsafe shell
constructs (curl|sh, eval, rm -rf, dd to disk, nc -e, …). This gate applies the
same rules at the PreToolUse boundary so an interactive Bash call gets the same
treatment as a hooks.json command. One source of truth — adding a pattern in
secscan.hook_injection auto-flows here.

Installed for every preset/dev_mode combo; the rules are defensive defaults
that no project should need to opt out of.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_maker.i18n import resolve_locale, t
from harness_maker.secscan.hook_injection import _DANGER_PATTERNS

_TRIGGER_TOOL = "Bash"

# Only Bash commands are checked against danger patterns (ADR-006). Non-Bash
# tool calls (write_file, apply_patch, …) are allowed because Codex's kernel
# sandbox (Seatbelt on macOS, Landlock on Linux) enforces filesystem access
# policy for those; the permission gate is a Bash-specific safety net only.
# Future work: extend to apply_patch once Codex sandbox compatibility is
# verified in tests/codex-compat/.
_KNOWN_HOOK_EVENTS = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "PreCompact",
        "Stop",
        "PermissionRequest",
    }
)


@dataclass(frozen=True)
class GateDecision:
    """Pure outcome — main() converts to exit code + stderr."""

    allow: bool
    matched_pattern: str  # category id from _DANGER_PATTERNS, "" when allowed
    message: str


def find_dangerous_pattern(command: str) -> tuple[str, re.Pattern[str]] | None:
    """Return the first (category, pattern) pair that fires, or None when safe."""
    for category, pattern in _DANGER_PATTERNS:
        if pattern.search(command):
            return category, pattern
    return None


def evaluate(
    tool_name: str,
    tool_input: dict[str, Any],
    project_dir: Path,
) -> GateDecision:
    """Evaluate a PreToolUse call; only Bash with a string command is checked."""
    if tool_name != _TRIGGER_TOOL:
        return GateDecision(allow=True, matched_pattern="", message="")
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return GateDecision(allow=True, matched_pattern="", message="")
    hit = find_dangerous_pattern(command)
    if hit is None:
        return GateDecision(allow=True, matched_pattern="", message="")
    category, _pattern = hit
    locale = resolve_locale(project_dir)
    msg = t("permission_gate_blocked", locale, pattern=category)
    return GateDecision(allow=False, matched_pattern=category, message=msg)


def main() -> int:
    """Entry point: read hook JSON from stdin.

    PreToolUse (Claude Code/Cursor): exit 0 (allow) or 2 (block).
    PermissionRequest (Codex): always exit 0; emit JSON hookSpecificOutput to stdout.
    """
    try:
        text = sys.stdin.read()
        payload: Any = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    hook_event = str(payload.get("hook_event_name") or "")
    if hook_event and hook_event not in _KNOWN_HOOK_EVENTS:
        # Unknown event — new Codex version or spoofed field. Safe default: allow.
        return 0
    tool_name = str(payload.get("tool_name") or "")
    raw_input = payload.get("tool_input")
    tool_input = raw_input if isinstance(raw_input, dict) else {}
    decision = evaluate(tool_name, tool_input, Path.cwd())
    if hook_event == "PermissionRequest":
        behavior = "allow" if decision.allow else "deny"
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PermissionRequest",
                        "decision": {"behavior": behavior},
                    }
                }
            )
        )
        return 0
    if decision.message:
        print(decision.message, file=sys.stderr)
    return 0 if decision.allow else 2


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess in tests
    sys.exit(main())
