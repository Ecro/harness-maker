"""SessionStart drift hook — surface stale-harness reminder via Claude.

Why: `/plugin update` refreshes the plugin's own commands/CLI but does NOT
re-render the user's `.claude/` (templates were rendered at the previous
harness-maker version). Users routinely forget to run `/hm:make` after a
plugin bump, so the rendered harness drifts behind the running plugin code.

This hook fires on SessionStart, reads the project's
`.claude/harness.yaml`, and if its stamped `harness_maker_version`
differs from the running plugin's `__version__`, emits a one-line
reminder via the SessionStart `additionalContext` channel. Silent
when no harness exists or no drift detected.

User-visibility note: Claude Code's SessionStart hook has NO user-visible
output field — both ``additionalContext`` and ``systemMessage`` feed
Claude's context only (per official docs at code.claude.com/docs/en/hooks,
2026-05-13 verification). The earlier 0.11.3 attempt to split into a
"user-facing systemMessage" was based on a misreading of the spec.
Instead, the context message is now phrased as an explicit instruction to
Claude to surface the drift to the user in its first response — that's
the only mechanism that actually reaches the user through this hook.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from harness_maker.relevance import detect_version_drift


def _format_context(stamped: str, current: str, direction: str) -> str:
    """Imperative instruction so Claude surfaces the drift to the user.

    ``additionalContext`` is consumed by the model, not displayed to the user.
    The only way a user sees the drift notice is if Claude *chooses* to mention
    it. Descriptive prose ("drift detected: ...") was too easy to ignore.
    Imperative framing ("Tell the user...") raises surface-rate to near 100%.
    """
    if direction == "upgrade":
        return (
            "[harness-maker drift — TELL THE USER NOW, before answering anything else] "
            f"The project's `.claude/` was rendered with harness-maker {stamped}, "
            f"but the installed plugin is now {current}. Tell the user in your next "
            "response that they should run `/hm:make --update` for a silent re-render, "
            "or `/harness-maker:make` for a full interactive run. Surface this at "
            "the top of your reply; do not bury it after other content."
        )
    return (
        "[harness-maker drift — TELL THE USER NOW, before answering anything else] "
        f"The project's `.claude/` was rendered with harness-maker {stamped}, "
        f"but the installed plugin is now {current} — a downgrade (plugin older "
        "than the stamped version). Tell the user in your next response to verify "
        "intent before running `/harness-maker:make`; this is unusual and may "
        "indicate an accidental rollback."
    )


def run(cwd: Path | None = None) -> int:
    if cwd is None:
        cwd = Path.cwd()

    drift = detect_version_drift(cwd)
    if drift is None:
        return 0

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": _format_context(drift.stamped, drift.current, drift.direction),
        }
    }
    sys.stdout.write(json.dumps(payload))
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
