"""Session-scoped `.hm-autopilot` marker for pipeline auto-advance (Phase 2)."""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from harness_maker import command_registry
from harness_maker.io_utils import atomic_write
from harness_maker.models import AtomicStage, AutonomyConfig
from harness_maker.worktree import (
    WORKTREE_DIR_NAME,
    _current_session_uuid,
    _ensure_gitignore_entry,
)

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

    @field_validator("pipeline")
    @classmethod
    def _pipeline_no_duplicates(cls, v: list[AtomicStage]) -> list[AtomicStage]:
        # autopilot_caps.next_stage() resolves by first index, so a duplicate stage makes
        # the chain loop forever once the runaway caps are unlimited (PLAN-autopilot-config-
        # surface Codex review P1). Reject duplicates so a marker — whoever wrote it (autoarm
        # hook, `autopilot on --pipeline`, picker) — can only advance monotonically to the
        # wrapup merge-gate. A duplicate pipeline → ValidationError → the autoarm hook's
        # try/except fail-safe-skips the arm.
        if len(v) != len(set(v)):
            raise ValueError("pipeline must not contain duplicate stages")
        return v


def marker_path(project_root: Path) -> Path:
    """WHY: single source for the marker location so callers never hardcode it."""
    return project_root / _MARKER_REL


def _is_harness_root(p: Path) -> bool:
    """A directory is a harness PROJECT root iff it carries ``.claude/harness.yaml``.

    The strict sentinel used for the ``.worktrees`` strip-base: a task worktree's base
    is always a harness project (it owns the `.worktrees/`), so a bare ``.git`` or a
    stray marker must NOT qualify the strip-base — otherwise a parent/home git repo
    (``~/.worktrees/proj`` with ``~`` a dotfiles repo) or a stale marker would capture
    resolution and write the marker into the wrong repo / silently disable the gate
    (REVIEW P2: security + codex consensus).
    """
    return (p / ".claude" / "harness.yaml").is_file()


def _is_marker_root(p: Path) -> bool:
    """A directory owns the marker iff it carries a project sentinel OR the marker.

    Used by the parent WALK (the non-worktree / standalone path). The project sentinel
    (``.claude/harness.yaml`` / ``.git``) lets the WRITE-first-arm resolve before any
    marker exists (plan-validator CRITICAL); an already-present marker is an additional
    accept so a read resolves to wherever the marker actually lives. The ``.worktrees``
    strip uses the stricter ``_is_harness_root`` instead (see ``resolve_marker_root``).
    """
    return (
        (p / _MARKER_REL).exists()
        or (p / ".claude" / "harness.yaml").is_file()
        or (p / ".git").exists()
    )


def resolve_marker_root(start: Path) -> Path:
    """Resolve the project root the autopilot marker lives at — worktree-aware.

    A ``/hm:`` stage runs inside ``.worktrees/<wt>/`` but the marker is owned by the
    base repo root (the SessionStart autoarm + the picker write it there, and the
    project-scoped ``session_uuid`` is keyed to it). Resolving cwd→base for EVERY
    op — read, write, clear — is what makes auto-advance see the marker from a
    worktree and `autopilot off` clear the real one.

    Sentinel-validated, NOT marker-existence-gated: the WRITE-first-arm from a
    worktree (no marker yet) must still resolve to the base, so the strip branch
    keys on a project sentinel, not on the marker file. The ``.worktrees`` strip is
    checked BEFORE the parent walk because a git worktree itself carries a ``.git``
    sentinel — walking first would wrongly stop at the worktree. The strip-base uses
    the STRICT ``_is_harness_root`` (``.claude/harness.yaml`` only) — not a bare
    ``.git`` / marker — so a parent/home git repo cannot capture resolution (REVIEW P2);
    a non-harness strip-base falls through to the walk, which finds the real project.

    Note: ``.absolute()`` (not ``.resolve()``) is deliberate — the strip is positional
    on ``.worktrees`` and ``.resolve()`` would canonicalise a symlinked worktree path,
    dropping the ``.worktrees`` component and breaking the strip (security-review).
    """
    start = Path(start).absolute()
    parts = start.parts
    if WORKTREE_DIR_NAME in parts:
        idx = len(parts) - 1 - parts[::-1].index(WORKTREE_DIR_NAME)
        if idx > 0:
            base = Path(*parts[:idx])
            if _is_harness_root(base):
                return base
    for directory in (start, *start.parents):
        if _is_marker_root(directory):
            return directory
    return start


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
    # Resolve cwd→base FIRST so both the marker path and the session_uuid below are
    # keyed to the project root — a write from inside a worktree lands at the base
    # (where reads look), not the worktree-local path (ADR-003 symmetric write).
    project_root = resolve_marker_root(project_root)
    marker = AutopilotMarker(
        session_uuid=_current_session_uuid(project_root),
        level=level,
        pipeline=list(pipeline),
        # `is not None` (not `or`): an explicit "" is preserved rather than silently
        # swapped for the live clock — keeps the injected-time contract honest.
        created_at=now if now is not None else datetime.now(UTC).isoformat(),
    )
    # P2-3: self-seed the gitignore entry at marker-creation time so the marker is never
    # committable even if `make` / `worktree create` (the other seed sites) never ran in
    # this project. Best-effort — a gitignore failure must not block arming autopilot.
    with contextlib.suppress(OSError):
        _ensure_gitignore_entry(project_root, _MARKER_REL)
    atomic_write(marker_path(project_root), marker.model_dump_json())
    return marker


def clear(project_root: Path) -> None:
    """Remove the marker; idempotent (no error when absent).

    Resolves cwd→base so `autopilot off` (and the boundary's terminal cap-halt /
    pipeline-complete / merge-gate clears) deletes the ROOT marker, never a
    worktree-local copy (Codex HIGH-2).
    """
    root = resolve_marker_root(project_root)
    marker_path(root).unlink(missing_ok=True)


def load(project_root: Path) -> AutopilotMarker | None:
    """Return the parsed marker, or None when absent / corrupt / schema-invalid.

    Fail-safe: ANY read or validation failure resolves to None (the caller treats
    None as gated). Does NOT check session ownership — see ``active_marker``.
    """
    path = marker_path(resolve_marker_root(project_root))
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


# A live autopilot session is short-lived; a marker older than this is treated as a
# crash leftover (REVIEW P1). Because `_current_session_uuid` is project-scoped, the
# uuid check alone cannot tell a crashed session's marker apart from the current one
# in the same project — the TTL is that fallback until the dirname-embed UUID migration.
_MARKER_TTL_HOURS = 18


def active_marker(project_root: Path, *, now: datetime | None = None) -> AutopilotMarker | None:
    """Return the marker ONLY when it belongs to the current session AND is fresh.

    A foreign/stale ``session_uuid`` (left by a crashed or different session) → None;
    a marker older than ``_MARKER_TTL_HOURS`` (or with an unparseable ``created_at``)
    → None. So autopilot never silently activates from another session's or a crashed
    session's leftover marker.

    NOTE: ``_current_session_uuid`` is project-scoped (worktree.py acknowledged
    limitation, ADR-004 §2) — within the SAME project the uuid is stable, so the TTL
    is the real cross-session guard until the dirname-embed UUID migration lands.
    """
    # Resolve once so the marker load AND the session_uuid comparison below agree on
    # the base root — a worktree's own uuid differs, so an unresolved compare would
    # foreign-reject the base marker (ADR-003).
    project_root = resolve_marker_root(project_root)
    marker = load(project_root)
    if marker is None:
        return None
    if marker.session_uuid != _current_session_uuid(project_root):
        logger.warning(".hm-autopilot: marker session_uuid mismatch (foreign) — ignoring.")
        return None
    moment = now if now is not None else datetime.now(UTC)
    try:
        created = datetime.fromisoformat(marker.created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age_s = (moment - created).total_seconds()
    except (ValueError, TypeError, OverflowError):
        logger.warning(".hm-autopilot: unparseable created_at — treating as stale.")
        return None
    # Reject BOTH a too-old marker (crash leftover) AND a future-dated one (clock skew
    # or a crafted created_at that would otherwise keep autopilot armed forever — a
    # negative age slips past a one-sided `> TTL` check). REVIEW round-2 P2.
    if age_s < 0 or age_s > _MARKER_TTL_HOURS * 3600:
        logger.warning(".hm-autopilot: marker outside the freshness window — ignoring.")
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


def resolve_toggle_config(
    level: str, pipeline: str | None
) -> tuple[Literal["gated", "auto_safe", "full"], list[AtomicStage]]:
    """Validate `--level` + `--pipeline` for an autopilot 'on'; raise ValueError on bad input.

    Shared by the Typer alias (`cli.autopilot_cmd`) and the dot-form entry (`main`) so the
    two entry points can never drift (PLAN-command-surface-registry ADR-003). Validates all
    inputs BEFORE any marker write so a failed 'on' leaves no partial/stale marker.
    """
    if level not in ("gated", "auto_safe", "full"):
        raise ValueError(f"invalid --level {level!r} (gated|auto_safe|full)")
    if pipeline is None:
        # Canonical default (research…review, VERIFY, WRAPUP) — NOT list(AtomicStage), whose
        # enum order puts WRAPUP before VERIFY. Single source of truth.
        stages = list(AutonomyConfig().pipeline)
    else:
        try:
            stages = [AtomicStage(s.strip()) for s in pipeline.split(",") if s.strip()]
        except ValueError as exc:
            raise ValueError(f"invalid --pipeline ({exc})") from None
    return cast("Literal['gated', 'auto_safe', 'full']", level), stages


def main(argv: list[str] | None = None) -> int:
    """Dot-form entry: `python -m harness_maker.autopilot on|off [...]`.

    Down-unified from the Typer `autopilot` toggle (ADR-001) so all `autopilot*` operations
    share the dominant `python -m harness_maker.<module>` convention. The Typer command
    survives as a thin backward-compat alias delegating to the same `resolve_toggle_config`
    + `write`/`clear`.
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    guard = command_registry.misroute_guard("autopilot", raw)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(add_help=False, prog="python -m harness_maker.autopilot")
    parser.add_argument("action", choices=["on", "off"])
    parser.add_argument("--level", default="auto_safe")
    parser.add_argument("--pipeline", default=None)
    parser.add_argument("--root", default=None)
    args = parser.parse_args(raw)
    root = Path(args.root) if args.root else Path.cwd()
    if args.action == "off":
        clear(root)
        print("autopilot: off (marker cleared)")
        return 0
    try:
        level, stages = resolve_toggle_config(args.level, args.pipeline)
    except ValueError as exc:
        print(f"autopilot: {exc}", file=sys.stderr)
        return 2
    try:
        marker = write(root, level=level, pipeline=stages)
    except ValidationError as exc:
        print(f"autopilot: invalid config ({exc})", file=sys.stderr)
        return 2
    print(f"autopilot: on (level={marker.level}, {len(marker.pipeline)} stages)")
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main(argv) in tests
    sys.exit(main())
