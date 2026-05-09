"""SessionStart drift hook — surface stale-harness reminder into Claude context.

Why: `/plugin update` refreshes the plugin's own commands/CLI but does NOT
re-render the user's `.claude/` (templates were rendered at the previous
harness-maker version). Users routinely forget to run `/hm:make` after a
plugin bump, so the rendered harness drifts behind the running plugin code.

This hook fires on SessionStart, reads the project's
`.claude/harness.yaml`, and if its stamped `harness_maker_version`
differs from the running plugin's `__version__`, emits a one-line
reminder via the SessionStart `additionalContext` channel. Silent
when no harness exists or no drift detected.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from harness_maker.relevance import detect_version_drift


def _format_message(stamped: str, current: str, direction: str) -> str:
    if direction == "upgrade":
        return (
            f"[harness-maker] Harness drift detected: project rendered with "
            f"{stamped}, plugin is at {current}. "
            f"Run /hm:make --update for a silent re-render, "
            f"or /harness-maker:make for a full interactive run."
        )
    return (
        f"[harness-maker] Harness drift detected: project rendered with "
        f"{stamped} but plugin is now at {current} (older than stamped). "
        f"Likely a plugin downgrade — verify intent before running /harness-maker:make."
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
            "additionalContext": _format_message(drift.stamped, drift.current, drift.direction),
        }
    }
    sys.stdout.write(json.dumps(payload))
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
