"""SessionStart hook — expose the Claude session_id to this session's Bash.

Why: slash-command Bash cannot read its own Claude ``session_id`` (no
``CLAUDE_SESSION_ID`` env var). The Stop-hook DOES receive ``session_id`` on
stdin, but the loop driver/marker writer (a slash command) does not — so a
session cannot key its own loop marker by its own id. This hook bridges the gap:
on SessionStart, Claude Code exposes ``CLAUDE_ENV_FILE`` whose ``KEY=value``
lines are sourced into every later Bash subprocess. We write the sanitized
session id as ``HM_SESSION_ID`` so ``/hm:loop`` can pass it to
``worktree create --claude-session-id`` and the marker becomes session-scoped
(PLAN-loop-marker-session-scoping ADR-002).

Fail-safe: any missing/degenerate input is a silent no-op (exit 0) — a hook
that blocks session start is worse than a degraded fallback (ADR-003). The
write is idempotent across resume/compact (overwrite the line, never append).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from harness_maker.loop_marker import sanitize_session_id

_ENV_KEY = "HM_SESSION_ID"


def _rewrite_env_file(env_file: Path, value: str) -> None:
    """Idempotently set ``HM_SESSION_ID=value`` — drop any prior line, append once.

    Atomic per CLAUDE.md (tempfile + os.replace via io_utils.atomic_write) so a
    crash mid-write cannot leave a half-line that breaks later sourcing.
    """
    from harness_maker.io_utils import atomic_write

    existing = ""
    if env_file.is_file():
        try:
            existing = env_file.read_text(encoding="utf-8")
        except OSError:
            existing = ""
    kept = [
        line
        for line in existing.splitlines()
        if line.strip() and not line.startswith(f"{_ENV_KEY}=")
    ]
    kept.append(f"{_ENV_KEY}={value}")
    atomic_write(env_file, "\n".join(kept) + "\n")


def run(stdin_text: str, env_file: Path | None) -> int:
    """Write the sanitized session id to ``env_file``; always exit 0."""
    if env_file is None:
        return 0
    try:
        data = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError:
        return 0
    if not isinstance(data, dict):
        return 0
    raw = data.get("session_id")
    if not isinstance(raw, str) or not raw:
        return 0
    sanitized = sanitize_session_id(raw)
    if not sanitized:
        return 0
    try:
        _rewrite_env_file(env_file, sanitized)
    except OSError:
        # Best-effort — never block session start (ADR-003).
        return 0
    return 0


def main() -> int:
    stdin_text = sys.stdin.read() if not sys.stdin.isatty() else ""
    raw_path = os.environ.get("CLAUDE_ENV_FILE")
    env_file = Path(raw_path) if raw_path else None
    return run(stdin_text, env_file)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
