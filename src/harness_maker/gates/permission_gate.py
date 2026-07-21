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
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_maker import autopilot
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


_SUBORDINATE_FLAG = "--subordinate-to-deny-dangerous"


def _resolve_project_dir(payload: dict[str, Any]) -> Path:
    """Resolve the harness project root (where `.claude/harness.yaml` lives).

    WHY not `Path.cwd()` (settles the REVIEW's codex-vs-security disagreement): a
    PreToolUse hook's cwd is NOT guaranteed to be the project root. This codebase already
    knows it — `autopilot.resolve_marker_root` exists precisely because "the hook
    subprocess's cwd is often a `.worktrees/<wt>/` dir during an autonomous execute", and
    a user can fire Bash from any subdirectory. Rooting the harness.yaml lookup at cwd
    would miss the file in both cases and fall to the fail-closed branch → unconditional
    blocking, silently defeating the `deny_dangerous` opt-out (codex's failure mode; it
    is real). The PreToolUse payload carries `cwd` / `workspace.current_dir` and Claude
    Code sets `$CLAUDE_PROJECT_DIR`; `resolve_marker_root` walks those up (and across
    `.worktrees/`) to the base repo. `Path.cwd()` is the last-resort fallback only.
    """
    raw_ws = payload.get("workspace")
    ws: dict[str, Any] = raw_ws if isinstance(raw_ws, dict) else {}
    start = Path(
        ws.get("current_dir")
        or payload.get("cwd")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CURSOR_PROJECT_DIR")
        or os.getcwd()
    )
    return autopilot.resolve_marker_root(start)


def _deny_dangerous_enabled(project_dir: Path) -> bool:
    """Is the gate switched on for this project? (ADR-007)

    Fail CLOSED to today's behavior: an UNREADABLE config (absent file, parse error,
    non-mapping) returns True, because unknown is not permission.

    A *readable* config with no ``permissions`` key is a different case and returns
    False — that is the documented default (``PermissionsConfig.deny_dangerous``, the
    2026-05-31 solo-friendly opt-out). Conflating the two would silently re-impose
    blocking on every harness that never set the key, i.e. most of them.
    """
    from harness_maker.io_utils import load_harness_yaml

    try:
        cfg = load_harness_yaml(project_dir / ".claude" / "harness.yaml")
    except Exception:  # noqa: BLE001 — any read/parse failure is "unknown" ⇒ fail closed
        return True
    if not isinstance(cfg, dict):
        return True
    perms = cfg.get("permissions")
    if perms is None:
        return False  # readable + key absent ⇒ the documented default
    if not isinstance(perms, dict):
        return True  # present but malformed ⇒ unknown ⇒ fail closed
    return bool(perms.get("deny_dangerous", False))


def main() -> int:
    """Entry point: read hook JSON from stdin.

    PreToolUse (Claude Code/Cursor): exit 0 (allow) or 2 (block).
    PermissionRequest (Codex): always exit 0; emit JSON hookSpecificOutput to stdout.

    ``--subordinate-to-deny-dangerous`` (ADR-007) makes the gate honor
    ``harness.yaml permissions.deny_dangerous``. It is rendered ONLY by the Claude
    settings template, because consumers are NOT distinguishable at runtime: Codex sends
    the byte-identical ``hook_event_name: "PreToolUse"`` (tests/codex-compat/
    hook_pre_tool_use_allow.json), so branching on the payload would subordinate Codex
    too — the regression this exists to prevent. Distinguishing at the PRODUCER keeps the
    Cursor and Codex invocations byte-unchanged, hence provably unregressed.

    Flag ABSENT ⇒ unconditional, i.e. today's behavior. Do not change that default.
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
    project_dir = _resolve_project_dir(payload)
    if _SUBORDINATE_FLAG in sys.argv and not _deny_dangerous_enabled(project_dir):
        return 0
    decision = evaluate(tool_name, tool_input, project_dir)
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
