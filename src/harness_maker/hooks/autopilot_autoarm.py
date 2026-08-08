"""SessionStart hook — re-arm autopilot when harness.yaml opts into persistence (ADR-003).

Why: the ``.hm-autopilot`` marker is deliberately ephemeral (18h TTL, session-scoped) so a
stale/foreign ``full``-auto never silently fires. That makes the user re-run
``harness-maker autopilot on`` every session. When ``autonomy.autopilot_persistent: true`` is
committed, this hook re-arms a FRESH marker each SessionStart from the committed level +
pipeline, so the TTL is reset every session and never trips in practice — while keeping the
marker's clear-on-terminal-halt + ownership semantics. The committed ``false`` is the real
off-switch (PLAN-autopilot-config-surface ADR-003).

Re-arm truth table: persistent-false → no arm; ``gated`` → no-op (gated never auto-advances);
``ask`` → no arm (the picker owns that session); any level in ``models.ARMED_LEVELS`` — today
``auto_safe`` and ``auto_full``, plus the legacy ``full`` spelling — → arm. Fail-safe: a
missing/malformed harness.yaml, an
invalid pipeline, or a write failure is a silent no-op (never raises) — a hook that blocks
SessionStart is worse than a degraded fallback.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from harness_maker import autopilot
from harness_maker.io_utils import load_harness_yaml
from harness_maker.loop_marker import sanitize_session_id
from harness_maker.models import (
    ARMED_LEVELS,
    LEGACY_LEVEL_ALIASES,
    AtomicStage,
    AutonomyConfig,
)

logger = logging.getLogger(__name__)


def arm_if_persistent(
    project_root: Path, *, now: str | None = None, claude_session_id: str | None = None
) -> bool:
    """Re-arm the marker iff ``autonomy.autopilot_persistent`` is true and the level is armable.

    Returns True iff a fresh marker was written. ANY failure → False, no raise (fail-safe).

    ``claude_session_id`` MUST be threaded through from the SessionStart payload. This hook
    runs as a sibling of `sessionid_envfile`, which publishes the id to ``$CLAUDE_ENV_FILE``
    for *later Bash subprocesses* — so ``HM_SESSION_ID`` is absent from THIS process. Left to
    the env lookup, the marker is stamped id-less and the arming session itself then reads it
    as foreign, wedging autopilot for the whole TTL with no in-band recovery.
    """
    yaml_path = project_root / ".claude" / "harness.yaml"
    try:
        cfg = load_harness_yaml(yaml_path)
    except Exception:
        return False
    if not isinstance(cfg, dict):
        return False
    autonomy = cfg.get("autonomy")
    if not isinstance(autonomy, dict):
        return False
    # `is True` (not truthy): a hand-edited "true" string or 1 must NOT arm — only a real bool.
    if autonomy.get("autopilot_persistent") is not True:
        return False
    # The ladder this replaced enumerated the arming levels by hand, so `auto_full` — the
    # flagship level — would have fallen through its `else: return False` and silently never
    # armed. `_ARMED_LEVELS` is derived from `OPERATIONAL_LEVELS`, so a new level arms by
    # existing. `ask` is absent from that tuple by construction: the picker owns that session
    # (ADR-003), and arming a marker here would answer a question that was meant to be asked.
    level = LEGACY_LEVEL_ALIASES.get(str(autonomy.get("level")), autonomy.get("level"))
    if level not in ARMED_LEVELS:
        return False
    pipeline_raw = autonomy.get("pipeline")
    try:
        if isinstance(pipeline_raw, list) and pipeline_raw:
            pipeline = [AtomicStage(stage) for stage in pipeline_raw]
        else:
            pipeline = list(AutonomyConfig().pipeline)
        autopilot.write(
            project_root,
            level=level,
            pipeline=pipeline,
            now=now,
            claude_session_id=claude_session_id,
        )
    except autopilot.MarkerOwnedByAnotherSessionError:
        # PLAN-multisession-marker-scoping ADR-009: since ADR-001 keyed the marker
        # FILENAME by session, an id-bearing session writes to a path no peer can occupy,
        # so this branch no longer fires for it — and that matters, because this is the
        # SessionStart auto-arm path for every `autopilot_persistent: true` harness, i.e.
        # exactly where two sessions previously fought over one file and the second was
        # silently left un-armed for the whole TTL.
        #
        # What remains reachable is the ADR-002 degraded fallback: two id-less callers
        # (Cursor, Codex, a failed `sessionid_envfile` hook) legitimately share
        # `.hm-autopilot-degraded`, and there is no per-session key to separate them. Do
        # not force — forcing would disarm the live peer that owns it.
        #
        # WARNING, not INFO: nothing in this package configures logging, so the root
        # logger sits at WARNING and `logging.lastResort` also fires only at WARNING+.
        # An INFO record here would be discarded outright — strictly LESS visible than
        # the generic fail-safe below, which is the opposite of "logged distinctly".
        logger.warning(
            ".hm-autopilot autoarm: the shared degraded marker is held by another "
            "id-less session — not arming (no session id available to key one)."
        )
        return False
    except Exception:
        logger.warning(".hm-autopilot autoarm: re-arm failed — skipping (fail-safe).")
        return False
    return True


def _session_id_from_stdin() -> str | None:
    """Sanitized ``session_id`` off the SessionStart payload; None on anything unusable.

    Mirrors `sessionid_envfile.run`'s read — the payload is this hook's only source for the
    id, since the env var that sibling publishes lands in later Bash, not here.
    """
    try:
        raw_text = sys.stdin.read() if not sys.stdin.isatty() else ""
        data = json.loads(raw_text) if raw_text.strip() else {}
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("session_id")
    if not isinstance(raw, str):
        return None
    return sanitize_session_id(raw) or None


def main() -> int:
    """SessionStart entrypoint — always exit 0 (a hook must never block session start)."""
    try:
        arm_if_persistent(Path.cwd(), claude_session_id=_session_id_from_stdin())
    except Exception:
        logger.warning(".hm-autopilot autoarm: unexpected error — ignored (fail-safe).")
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main() in tests
    sys.exit(main())
