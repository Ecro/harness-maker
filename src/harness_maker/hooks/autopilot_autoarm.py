"""SessionStart hook — re-arm autopilot when harness.yaml opts into persistence (ADR-003).

Why: the ``.hm-autopilot`` marker is deliberately ephemeral (18h TTL, session-scoped) so a
stale/foreign ``full``-auto never silently fires. That makes the user re-run
``harness-maker autopilot on`` every session. When ``autonomy.autopilot_persistent: true`` is
committed, this hook re-arms a FRESH marker each SessionStart from the committed level +
pipeline, so the TTL is reset every session and never trips in practice — while keeping the
marker's clear-on-terminal-halt + ownership semantics. The committed ``false`` is the real
off-switch (PLAN-autopilot-config-surface ADR-003).

Re-arm truth table: persistent-false → no arm; ``gated`` level → no-op (gated never
auto-advances); ``auto_safe``/``full`` → arm. Fail-safe: a missing/malformed harness.yaml, an
invalid pipeline, or a write failure is a silent no-op (never raises) — a hook that blocks
SessionStart is worse than a degraded fallback.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Literal

from harness_maker import autopilot
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import AtomicStage, AutonomyConfig

logger = logging.getLogger(__name__)


def arm_if_persistent(project_root: Path, *, now: str | None = None) -> bool:
    """Re-arm the marker iff ``autonomy.autopilot_persistent`` is true and the level is armable.

    Returns True iff a fresh marker was written. ANY failure → False, no raise (fail-safe).
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
    # Narrow to the Literal via ``==`` (mypy-strict-friendly). ``gated``/unknown → no-op: a
    # gated marker never auto-advances, so arming it only adds marker noise.
    level = autonomy.get("level")
    armed_level: Literal["gated", "auto_safe", "full"]
    if level == "auto_safe":
        armed_level = "auto_safe"
    elif level == "full":
        armed_level = "full"
    else:
        return False
    pipeline_raw = autonomy.get("pipeline")
    try:
        if isinstance(pipeline_raw, list) and pipeline_raw:
            pipeline = [AtomicStage(stage) for stage in pipeline_raw]
        else:
            pipeline = list(AutonomyConfig().pipeline)
        autopilot.write(project_root, level=armed_level, pipeline=pipeline, now=now)
    except Exception:
        logger.warning(".hm-autopilot autoarm: re-arm failed — skipping (fail-safe).")
        return False
    return True


def main() -> int:
    """SessionStart entrypoint — always exit 0 (a hook must never block session start)."""
    try:
        arm_if_persistent(Path.cwd())
    except Exception:
        logger.warning(".hm-autopilot autoarm: unexpected error — ignored (fail-safe).")
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main() in tests
    sys.exit(main())
