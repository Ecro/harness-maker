"""PostToolUse hook — surfaces a one-line reminder after Write/Edit on watched paths.

Lightweight by design (≤100ms typical). Reads the tool input from stdin (Claude Code
hook protocol), checks the written path against a STATIC, vendor-defined rule list,
emits a single reminder line on stdout when matched.

Never blocks the tool call — this hook is advisory only.

Security note: this hook intentionally does NOT ingest user-writable content
(wiki.md gotcha entries, project-defined rules) into its stdout. The hook's stdout
is read back into the next LLM turn as tool output; emitting unsanitised user-
authored text would create a stored-prompt-injection vector. The static
``_DEFAULT_RULES`` list is the sole source of reminder text.
"""

from __future__ import annotations

import json
import sys

# Domain-keyed reminder rules. Matched against the written file's path components.
# Each rule is (path_keyword, reminder_text).
#
# **HARD INVARIANT:** Both fields are static, vendor-controlled strings. Never
# extend this list at runtime from a file the user can author (wiki.md, harness.yaml,
# .env, etc.) — the reminder text flows verbatim to the LLM's next turn.
_DEFAULT_RULES: list[tuple[str, str]] = [
    (
        "auth",
        "auth touched — verify session-token storage + role-check; run security tests.",
    ),
    (
        "secret",
        "secret-handling code touched — confirm nothing logs the secret; check rotation path.",
    ),
    (
        "password",
        "password code touched — verify hashing algorithm + comparison is constant-time.",
    ),
    (
        "hook",
        "hook touched — re-render harness or restart Claude Code for it to take effect.",
    ),
    (
        "worker",
        "worker / thread code touched — walk lock acquisition order and ISR-context calls.",
    ),
    (
        "isr",
        "ISR code touched — confirm no allocations / no blocking calls / stack budget OK.",
    ),
    (
        "migration",
        "DB migration touched — verify backwards-compat with the previous version's reads.",
    ),
    (
        "schema",
        "schema touched — bump version + write migration when older clients still read it.",
    ),
    (".env", ".env touched — confirm it's gitignored; re-check secret leakage risk."),
    (
        "settings.json",
        "settings.json touched — Claude Code reads at session start; restart to pick up.",
    ),
    (
        "hooks.json",
        "hooks.json touched — restart Claude Code for the new hook config to load.",
    ),
]


def _read_tool_input() -> dict[str, object]:
    """Read JSON from stdin (Claude Code hook protocol). Empty / malformed → empty dict."""
    try:
        raw = sys.stdin.read()
        if not raw:
            return {}
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _extract_written_path(payload: dict[str, object]) -> str | None:
    """Pull the `file_path` from the tool input. Schema differs across tools."""
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return None
    for key in ("file_path", "path", "notebook_path"):
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def _match_rules(file_path: str, rules: list[tuple[str, str]]) -> list[str]:
    """Return reminder texts whose keyword matches any path component (case-insensitive)."""
    lowered = file_path.lower()
    matched: list[str] = []
    for keyword, text in rules:
        if keyword.lower() in lowered:
            matched.append(text)
    return matched


def main() -> int:
    """Hook entry. Emits reminders on stdout; never blocks the tool call."""
    payload = _read_tool_input()
    file_path = _extract_written_path(payload)
    if not file_path:
        return 0
    reminders = _match_rules(file_path, _DEFAULT_RULES)
    if not reminders:
        return 0
    msg = "[post-write-reminder] " + " | ".join(reminders[:3])
    print(msg, file=sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
