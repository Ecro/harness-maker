"""Session-scoped `.hm-autopilot` marker for pipeline auto-advance (Phase 2)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from harness_maker.io_utils import atomic_write
from harness_maker.models import AtomicStage
from harness_maker.worktree import _current_session_uuid

logger = logging.getLogger(__name__)

# Grouped with `.claude/.hm-session-uuid` so the existing `.claude/` gitignore
# coverage + the churn-file dirt-filters apply (registered in
# worktree._HARNESS_CHURN_FILES — see test_marker_is_in_churn_files).
_MARKER_REL = ".claude/.hm-autopilot"


class AutopilotMarker(BaseModel):
    """On-disk session autopilot state.

    ADR-006: the session-start answer (``level`` + ``pipeline``) is persisted HERE,
    keyed by ``session_uuid``. A marker whose ``session_uuid`` does not match the
    current session's UUID is ignored (fail-safe → gated), mirroring the worktree
    layer-3 cross-session defense. ``strict``/``forbid`` so a hand-edited or
    truncated marker fails validation and is dropped rather than half-honored.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    session_uuid: str = Field(pattern=r"^[0-9a-f]{12}$")
    level: Literal["gated", "auto_safe", "full"]
    # min_length=1: an empty pipeline is a silent no-op for the Phase 3+ stop-hook
    # (autopilot "on" but never advances) — reject it as a malformed marker instead.
    pipeline: list[AtomicStage] = Field(min_length=1)
    created_at: str


def marker_path(project_root: Path) -> Path:
    """WHY: single source for the marker location so callers never hardcode it."""
    return project_root / _MARKER_REL


def write(
    project_root: Path,
    *,
    level: Literal["gated", "auto_safe", "full"],
    pipeline: list[AtomicStage],
    now: str | None = None,
) -> AutopilotMarker:
    """Persist the session autopilot answer, stamped with the current session UUID.

    ``now`` is injectable for deterministic tests (checkpoint 7); defaults to the
    current UTC time in ISO-8601.
    """
    marker = AutopilotMarker(
        session_uuid=_current_session_uuid(project_root),
        level=level,
        pipeline=list(pipeline),
        # `is not None` (not `or`): an explicit "" is preserved rather than silently
        # swapped for the live clock — keeps the injected-time contract honest.
        created_at=now if now is not None else datetime.now(UTC).isoformat(),
    )
    atomic_write(marker_path(project_root), marker.model_dump_json())
    return marker


def clear(project_root: Path) -> None:
    """Remove the marker; idempotent (no error when absent)."""
    marker_path(project_root).unlink(missing_ok=True)


def load(project_root: Path) -> AutopilotMarker | None:
    """Return the parsed marker, or None when absent / corrupt / schema-invalid.

    Fail-safe: ANY read or validation failure resolves to None (the caller treats
    None as gated). Does NOT check session ownership — see ``active_marker``.
    """
    path = marker_path(project_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(".hm-autopilot: unreadable/corrupt marker ignored (%s).", e)
        return None
    try:
        # strict=False so the JSON pipeline strings coerce into AtomicStage (the
        # model is strict=True, which would reject str→enum); the level Literal,
        # the session_uuid pattern, and extra="forbid" still reject bad markers.
        return AutopilotMarker.model_validate(data, strict=False)
    except ValidationError as e:
        logger.warning(".hm-autopilot: invalid marker ignored (%s).", e)
        return None


def active_marker(project_root: Path) -> AutopilotMarker | None:
    """Return the marker ONLY when it belongs to the current session.

    A foreign/stale ``session_uuid`` (left by a crashed or different session) →
    None, so autopilot never silently activates from another session's marker.

    NOTE: ``_current_session_uuid`` is project-scoped (worktree.py acknowledged
    limitation, ADR-004 §2) — so within the SAME project the uuid is stable and
    cross-session isolation does not yet fire; the dirname-embed UUID migration
    closes that. The fail-safe against corrupt/absent/wrong-shape markers (via
    ``load``) is unaffected and fires today.
    """
    marker = load(project_root)
    if marker is None:
        return None
    if marker.session_uuid != _current_session_uuid(project_root):
        logger.warning(
            ".hm-autopilot: marker session_uuid mismatch (foreign/stale) — ignoring.",
        )
        return None
    return marker


_VALID_LEVELS = frozenset({"gated", "auto_safe", "full"})


def effective_level(project_root: Path, *, yaml_level: str) -> str:
    """Precedence resolver (ADR-006): an active session marker wins over harness.yaml.

    ADR-006's three logical surfaces collapse to two mechanisms: the session-start
    answer is persisted INTO the marker at ``write()`` time, so the active-marker
    check subsumes both the marker and the start-answer tiers; the only fallback is
    the committed ``harness.yaml`` ``autonomy.level``.

    A live marker overrides the committed default; an absent/foreign/invalid marker
    falls back to ``yaml_level`` — but a ``yaml_level`` that is not one of the three
    known levels (typo, empty, pre-feature default) is itself unsafe to honor, so it
    is clamped to ``"gated"`` (fail-safe; absent-case = feature black hole guard).
    """
    marker = active_marker(project_root)
    if marker is not None:
        return marker.level
    if yaml_level not in _VALID_LEVELS:
        logger.warning(".hm-autopilot: unknown yaml autonomy.level %r → gated.", yaml_level)
        return "gated"
    return yaml_level
