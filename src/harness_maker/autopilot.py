"""Session-scoped `.hm-autopilot` marker for pipeline auto-advance (Phase 2)."""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from harness_maker import command_registry, loop_marker
from harness_maker.io_utils import atomic_write
from harness_maker.models import AtomicStage, AutonomyConfig
from harness_maker.worktree import (
    WORKTREE_DIR_NAME,
    _current_session_uuid,
    _ensure_gitignore_entry,
)

logger = logging.getLogger(__name__)

# PLAN-multisession-marker-scoping ADR-001: the marker is ONE FILE PER SESSION, keyed by
# the sanitized `claude_session_id` — the same key `loop_marker.py` uses. A single shared
# path made two concurrent sessions structurally unable to both be armed, and escalated
# that to the user as a question ("is another session open?") whose honest answer on the
# normal path is always yes.
#
# ADR-011: the dirt-filter + gitignore coverage moved from an EXACT literal in
# `worktree._HARNESS_CHURN_FILES` to a PREFIX in `_HARNESS_ARTIFACT_PREFIXES` plus a
# `.claude/.hm-autopilot*` gitignore glob — a per-session filename matches neither of the
# old exact entries, and without the prefix every live marker becomes user dirt that
# `worktree finalize` sweeps into the finalize stash (a silent disarm).
_MARKER_DIR = ".claude"
_MARKER_BASENAME = ".hm-autopilot"
# ADR-002: id-less callers (Cursor, Codex, a failed SessionStart hook) share ONE marker,
# under a name DISTINCT from the legacy path below — ADR-003 unlinks the legacy path, and
# reusing that name as the fallback would delete a live degraded session's marker.
_DEGRADED_BASENAME = f"{_MARKER_BASENAME}-degraded"
# ADR-003: the pre-upgrade single-file path. Read once, taken over, then unlinked under a
# compare-and-swap. Nothing else may read it.
_LEGACY_MARKER_REL = f"{_MARKER_DIR}/{_MARKER_BASENAME}"
# NB: no hyphen before the `*` — `.hm-autopilot-*` would stop covering the bare legacy
# name, which stays alive until every project has taken it over.
_MARKER_GITIGNORE_GLOB = f"{_MARKER_DIR}/{_MARKER_BASENAME}*"

# The per-SESSION key (PLAN-autopilot-advance-noop ADR-007). `session_uuid` below is
# PROJECT-scoped, so within one project every session reads every other session's marker
# as its own — autopilot silently INHERITED, the mirror of the silently-off bug. This is
# the same id `loop_marker.py` keys on, exported by the `sessionid_envfile` SessionStart
# hook.
_SESSION_ID_ENV = "HM_SESSION_ID"

# Same PATTERN as `worktree._TASK_SLUG_RE` — the slug this marker carries is the one the
# task worktree is named for. Applied with `fullmatch` here, so this surface accepts a
# strict subset of what worktree's `match` does (see `_task_slug_charset`).
_TASK_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class MarkerOwnedByAnotherSessionError(RuntimeError):
    """Raised by ``write`` when a LIVE marker belongs to a different session (ADR-010).

    Without this, arming is an unconditional ``atomic_write``: session B's picker would
    stamp its own identity over session A's live marker, and A's next boundary check would
    judge that marker foreign → ``kill_switch`` → A's chain dies mid-pipeline with no
    diagnostic. The GC restraint in ADR-008 alone never closed this path.
    """


def _env_session_id() -> str | None:
    """The caller's Claude session id, or None when degraded/absent.

    An empty/whitespace value is None, NOT "": a degraded environment (Cursor, Codex,
    SessionStart-hook failure) must land in the both-idless fallback rather than matching
    another degraded session's empty string.
    """
    raw = os.environ.get(_SESSION_ID_ENV, "").strip()
    return raw or None


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
    # All three default to None so a pre-upgrade marker still validates under
    # `extra="forbid"` (CLAUDE.md absent-case rule). `task_slug` rides to the next stage's
    # `Skill(hm:<stage> <slug>)` call — without it, argument-parsing stages start blank and
    # stall, which reads to the user as "announced but did nothing" (ADR-003).
    # `task_slug_stage` records which stage supplied it, so an inherited slug is
    # attributable rather than silent.
    task_slug: str | None = Field(default=None, max_length=128)
    task_slug_stage: str | None = None
    claude_session_id: str | None = None
    # Heartbeat, refreshed by the OWNER at every autopilot CLI call (round-4 review).
    # Ownership alone cannot tell a live peer from an abandoned marker: nothing clears the
    # marker at session end (`clear` fires only on explicit `off` and the three terminal
    # boundary paths), so a session that armed and closed mid-pipeline left a `fresh`
    # marker that no one could take for the full 18h TTL — reinstating the silently-never-
    # arms defect this whole change exists to remove. This does NOT authorize automatic
    # takeover; it gives `status` a factual "last active N minutes ago" for the picker to
    # put to the user, who is the only party that knows whether another session is open.
    last_seen: str | None = None

    @field_validator("task_slug")
    @classmethod
    def _task_slug_charset(cls, v: str | None) -> str | None:
        # `task_slug` crosses TWO sinks: it is interpolated into the `!uv run … --slug …`
        # line of a rendered slash command (a shell), and the boundary JSON hands it back
        # as the argument of a `Skill(hm:<stage> <slug>)` instruction. Every comparable
        # slug surface in this repo is allowlisted (`worktree._TASK_SLUG_RE`,
        # `spec_need._SLUG_RE`, `memory_md`); this one was not, and it is the only one
        # that also round-trips through a marker replayed by every later stage.
        if v is None:
            return None
        # `fullmatch`, not `match`: `$` also matches BEFORE a trailing newline, so
        # `match` would accept "ok\n" — and this value is interpolated into a shell
        # command line. `worktree._TASK_SLUG_RE` uses `match`; this surface is
        # deliberately the stricter of the two rather than bug-compatible with it.
        if not _TASK_SLUG_RE.fullmatch(v) or ".." in v:
            raise ValueError(
                f"task_slug {v!r} must match {_TASK_SLUG_RE.pattern} and contain no '..'"
            )
        return v

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


def marker_path(project_root: Path, *, session_id: str | None) -> Path:
    """The calling session's marker file — single source, so callers never hardcode it.

    ``session_id`` is keyword-only and REQUIRED (no default) on purpose. A default would
    silently resolve a missed reader to the degraded fallback, which in a real Claude Code
    session means "autopilot is off" with no diagnostic — the exact shape of
    `[fail:design] new-marker-content-field-must-update-every-reader` (count:3). Passing
    ``None`` explicitly is the id-less case; forgetting to pass anything is a TypeError.

    The env lookup is kept as a fallback for a host that DOES export ``HM_SESSION_ID``
    (Claude Code does not — it is an unexported shell variable), matching every other
    reader in this module.
    """
    key = loop_marker.sanitize_session_id(session_id or _env_session_id() or "")
    # `sanitize_session_id` hashes anything that is not a tame hex/UUID id, so a session
    # literally named "degraded" is hashed and cannot collide with the fallback name.
    name = f"{_MARKER_BASENAME}-{key}" if key else _DEGRADED_BASENAME
    return project_root / _MARKER_DIR / name


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
    claude_dir = p / _MARKER_DIR
    has_marker = claude_dir.is_dir() and any(claude_dir.glob(f"{_MARKER_BASENAME}*"))
    return has_marker or (p / ".claude" / "harness.yaml").is_file() or (p / ".git").exists()


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
    force: bool = False,
    claude_session_id: str | None = None,
) -> AutopilotMarker:
    """Persist the session autopilot answer, stamped with the current session UUID.

    ``now`` is injectable for deterministic tests (checkpoint 7); defaults to the
    current UTC time in ISO-8601.

    ``force`` bypasses the ADR-010 ownership guard — for a user deliberately taking over
    a crashed peer's still-fresh marker. Absent it, overwriting a LIVE foreign marker
    raises rather than silently disarming that session.

    ``claude_session_id`` overrides the ``HM_SESSION_ID`` lookup for callers that hold the
    id but do not have it in their environment. The `autopilot_autoarm` SessionStart hook
    is exactly that case and the reason this parameter exists: its sibling hook
    `sessionid_envfile` publishes the id to ``$CLAUDE_ENV_FILE``, which Claude Code sources
    into *later Bash subprocesses* — never into a sibling hook's own process. Without the
    override, autoarm stamped ``claude_session_id: null``; the very session that armed it
    then read that marker as foreign (one-directional rule), so `autopilot_persistent`
    harnesses were wedged at `kill_switch` for the full TTL — and ADR-010's picker branch
    refuses to re-arm over a foreign marker, so there was no in-band recovery.
    """
    # Resolve cwd→base FIRST so both the marker path and the session_uuid below are
    # keyed to the project root — a write from inside a worktree lands at the base
    # (where reads look), not the worktree-local path (ADR-003 symmetric write).
    project_root = resolve_marker_root(project_root)
    effective_session_id = claude_session_id or _env_session_id()
    if not force:
        existing = load(project_root, session_id=effective_session_id)
        # `!= "stale"` — NOT `== "fresh"`. A `future` marker (clock rollback / NTP step / a
        # differently-skewed host on a shared tree) is one `gc_stale_marker` refuses to
        # delete precisely because it may be a peer's LIVE marker; letting `write` clobber
        # what the GC protects is the same peer-disarm through the other door. `unparseable`
        # is protected for the same reason and stays recoverable: `status` GCs it, and the
        # raise names `--force`.
        if (
            existing is not None
            and _freshness(existing.created_at) != "stale"
            and not _is_own(existing, project_root, session_id=effective_session_id)
        ):
            raise MarkerOwnedByAnotherSessionError(
                "a live .hm-autopilot marker belongs to another session — "
                "not overwriting (pass --force to take it over)"
            )
    marker = AutopilotMarker(
        session_uuid=_current_session_uuid(project_root),
        level=level,
        pipeline=list(pipeline),
        claude_session_id=effective_session_id,
        # `is not None` (not `or`): an explicit "" is preserved rather than silently
        # swapped for the live clock — keeps the injected-time contract honest.
        created_at=now if now is not None else datetime.now(UTC).isoformat(),
    )
    # P2-3: self-seed the gitignore entry at marker-creation time so the marker is never
    # committable even if `make` / `worktree create` (the other seed sites) never ran in
    # this project. Best-effort — a gitignore failure must not block arming autopilot.
    with contextlib.suppress(OSError):
        # The GLOB, not the resolved filename: one .gitignore line covers every session's
        # marker plus the legacy path, and the file is unbounded in count (ADR-011).
        _ensure_gitignore_entry(project_root, _MARKER_GITIGNORE_GLOB)
    atomic_write(
        marker_path(project_root, session_id=effective_session_id), marker.model_dump_json()
    )
    return marker


def other_keyed_markers(project_root: Path, *, session_id: str | None) -> list[str]:
    """Marker filenames in this project that `clear(session_id=...)` would NOT remove.

    Exists for one caller: the operator-facing `autopilot off`. ADR-013 scopes a session's
    unlink authority to its own key, which is right for peer isolation and wrong for a
    human typing the documented kill switch — that invocation has no `--session-id` (and
    `HM_SESSION_ID` is a shell variable `os.environ` never sees), so it resolves to the
    degraded key, unlinks nothing, and used to print success while the armed marker kept
    auto-advancing for the full TTL. Reporting requires knowing what was left behind.
    """
    claude_dir = project_root / _MARKER_DIR
    if not claude_dir.is_dir():
        return []
    keep = marker_path(project_root, session_id=session_id).name
    return sorted(
        p.name for p in claude_dir.glob(f"{_MARKER_BASENAME}*") if p.is_file() and p.name != keep
    )


def clear(project_root: Path, *, session_id: str | None) -> bool:
    """Remove THIS session's marker; idempotent. True iff a file was actually removed.

    The return value is load-bearing for `autopilot off`: an unconditional "marker cleared"
    over a no-op is how a documented kill switch becomes a lie.

    Resolves cwd→base so `autopilot off` (and the boundary's terminal cap-halt /
    pipeline-complete / merge-gate clears) deletes the ROOT marker, never a
    worktree-local copy (Codex HIGH-2).

    ADR-013: a session may unlink only its OWN key. Clearing by glob would make every
    session an unlink authority over every peer's marker — reversing, through the GC
    door, the isolation ADR-001 exists to create.
    """
    root = resolve_marker_root(project_root)
    path = marker_path(root, session_id=session_id)
    existed = path.is_file()
    path.unlink(missing_ok=True)
    return existed


def _takeover_legacy(project_root: Path, *, session_id: str | None) -> None:
    """One-shot ADR-003 migration of the pre-upgrade single-file marker.

    If this session has no per-session marker yet but the legacy `.claude/.hm-autopilot`
    exists and evaluates as OURS under today's rules, rewrite it at the per-session path
    and unlink the legacy file — but only if its bytes are unchanged since the read
    (compare-and-swap). Without the CAS a peer's replacement landing between the
    judgement and the unlink is destroyed; `gc_stale_marker`'s docstring records that
    this narrows and does not close the window, and the same is true here. The residual
    loss is one marker, recoverable by re-arming.

    Anything unexpected — unreadable, unparseable, foreign — leaves the legacy file
    alone. The compat branch is therefore self-erasing for the owner and inert for
    everyone else.
    """
    root = resolve_marker_root(project_root)
    target = marker_path(root, session_id=session_id)
    if target.exists():
        return
    legacy = root / _LEGACY_MARKER_REL
    try:
        raw = legacy.read_bytes()
    except OSError:
        return
    try:
        marker = AutopilotMarker.model_validate(json.loads(raw.decode("utf-8")), strict=False)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        return
    if not _is_own(marker, root, session_id=session_id or _env_session_id()):
        return
    try:
        atomic_write(target, marker.model_dump_json())
        if legacy.read_bytes() == raw:
            legacy.unlink(missing_ok=True)
        else:
            logger.warning(".hm-autopilot: legacy marker changed during takeover — kept.")
    except OSError:
        return


def load(project_root: Path, *, session_id: str | None) -> AutopilotMarker | None:
    """Return the parsed marker, or None when absent / corrupt / schema-invalid.

    Fail-safe: ANY read or validation failure resolves to None (the caller treats
    None as gated). Does NOT check session ownership — see ``active_marker``.

    NOT pure: it runs the one-shot ADR-003 legacy takeover first. This is the single
    choke point every read path passes through, so putting the migration anywhere else
    means some entry point silently reports "not armed" for a project that IS armed
    under the old filename.
    """
    root = resolve_marker_root(project_root)
    _takeover_legacy(root, session_id=session_id)
    path = marker_path(root, session_id=session_id)
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


Freshness = Literal["fresh", "stale", "future", "unparseable"]


def _freshness(created_at: str, now: datetime | None = None) -> Freshness:
    """Classify a marker's age. Single source for BOTH the reject and the delete rules.

    They are deliberately different verdicts on the same axis (ADR-008): ``active_marker``
    rejects anything not ``fresh`` — non-destructive, so a false positive costs nothing —
    while ``gc_stale_marker`` deletes ONLY ``stale``. ``future`` (clock rollback / NTP step
    / a differently-skewed host on a shared tree) must never be deletable: a peer's
    freshly-armed marker can present a negative age, and destroying it is exactly the
    silent disarm the GC restraint exists to prevent.
    """
    moment = now if now is not None else datetime.now(UTC)
    try:
        created = datetime.fromisoformat(created_at)
    except (ValueError, TypeError, OverflowError):
        return "unparseable"
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    try:
        age_s = (moment - created).total_seconds()
    except (OverflowError, OSError):  # pragma: no cover — pathological datetimes
        return "unparseable"
    if age_s < 0:
        # A real clock skew is BOUNDED — an NTP step or a differently-skewed host is
        # minutes to hours, not a year. Beyond one TTL of skew the marker is not credible
        # clock jitter, and treating it as permanently-protected `future` left a foreign
        # one neither collectable (GC preserves `future`) nor overwritable (the write guard
        # protects everything non-`stale`) — an unbounded wedge with no in-band exit.
        return "stale" if -age_s > _MARKER_TTL_HOURS * 3600 else "future"
    return "stale" if age_s > _MARKER_TTL_HOURS * 3600 else "fresh"


def _is_own(marker: AutopilotMarker, project_root: Path, *, session_id: str | None = None) -> bool:
    """Session ownership — ONE-DIRECTIONAL (ADR-007).

    Ids are compared whenever **either** side has one; the project-scoped uuid fallback
    applies only when **neither** does. A symmetric "compare only when both are present"
    rule would let an id-bearing session inherit a fieldless legacy marker — the direction
    `loop_marker` explicitly forbids ("honored only when the caller has no id of its own").

    ``session_id`` is the caller's EFFECTIVE id, for a caller that holds its id but does not
    have it in the environment — the `autopilot_autoarm` SessionStart hook, which receives
    it on stdin while `HM_SESSION_ID` reaches only later Bash. Without it that caller
    resolves as id-less and is foreign to every id-bearing marker, including the one it
    wrote itself moments earlier. `force` is NOT the answer to that: it would disable the
    guard for genuinely foreign markers too, so a second session opening in the same project
    would silently steal the first's marker at every SessionStart — the exact peer-disarm
    ADR-010 exists to prevent.
    """
    env_id = session_id or _env_session_id()
    marker_id = marker.claude_session_id or None
    if env_id is not None or marker_id is not None:
        return env_id is not None and marker_id is not None and env_id == marker_id
    return marker.session_uuid == _current_session_uuid(project_root)


def gc_stale_marker(project_root: Path, *, session_id: str | None) -> bool:
    """Delete THIS SESSION's marker iff it is TTL-stale (or unparseable). True when deleted.

    Kept OUT of ``active_marker`` on purpose: that predicate is documented pure and
    ``evaluate_boundary`` depends on it. GC is called from ``status`` and the picker path
    only — never from ``boundary``.

    Two restraints, both load-bearing:
      * **foreignness is not a criterion, in either direction.** After ADR-007 "foreign"
        means "another LIVE session", so deleting what ``active_marker`` rejects would
        disarm a peer. Equally, refusing to delete anything foreign would make a crashed
        peer's marker uncollectable forever — reinstating the stale-file-suppresses-arming
        defect this whole change removes.
      * **re-read before unlink.** A replacement written between the judgement and the
        unlink must survive, so the delete is gated on byte identity rather than on the
        judgement alone. This **narrows, and does not close,** the window: the re-read and
        the `unlink` are still two operations on a pathname, so a replacement landing
        between them is removed. Closing it needs an inode-level swap primitive this does
        not have; the residual race requires two sessions inside the same microseconds,
        and the loser re-arms via the picker.

    ADR-013 narrows the scope to the caller's own key. The two restraints below were
    argued for ONE shared file; applied over a glob they would authorize deleting a
    peer's marker, which is precisely what per-session files exist to prevent. Nothing
    here globs, so a crashed peer's marker survives THIS call and is simply inert — the
    operator sweep `gc_expired_markers` (via `worktree.prune_stale`) collects it once
    TTL-expired, which is what keeps `.claude/` from growing a file per session forever.

    ``OSError`` from the unlink propagates — ``status`` decides how to report it.
    """
    root = resolve_marker_root(project_root)
    path = marker_path(root, session_id=session_id)
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    try:
        marker = AutopilotMarker.model_validate(json.loads(raw.decode("utf-8")), strict=False)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        deletable = True  # a marker nothing can parse cannot belong to a live session
    else:
        # "unparseable" is a garbage `created_at` on an otherwise-valid marker. It must be
        # collectable: `active_marker` already rejects it, so leaving it on disk wedges the
        # project forever — the picker sees `foreign`/non-armed and, per ADR-010, refuses to
        # arm over it. "future" is the ONLY non-fresh state that stays (clock skew must not
        # let anyone delete a peer's live marker).
        deletable = _freshness(marker.created_at) in ("stale", "unparseable")
    if not deletable:
        return False
    try:
        if path.read_bytes() != raw:
            logger.warning(".hm-autopilot: marker changed during GC — not deleting.")
            return False
    except OSError:
        return False
    path.unlink()
    return True


def _some_id_bearing_marker(root: Path) -> AutopilotMarker | None:
    """Any parseable per-session marker carrying a session id. Diagnostic only.

    The ONE place that reads across marker files. It never writes and never unlinks
    (ADR-013 forbids the latter), and its single consumer is ``status``'s
    ``degraded-idless`` label — nothing branches on it, so a wrong answer costs a word
    in a diagnostic, not a decision.
    """
    claude_dir = root / _MARKER_DIR
    if not claude_dir.is_dir():
        return None
    for path in sorted(claude_dir.glob(f"{_MARKER_BASENAME}*")):
        try:
            marker = AutopilotMarker.model_validate(
                json.loads(path.read_text(encoding="utf-8")), strict=False
            )
        except (OSError, json.JSONDecodeError, ValidationError):
            continue
        if marker.claude_session_id:
            return marker
    return None


def gc_expired_markers(project_root: Path) -> list[str]:
    """Operator sweep: delete every TTL-EXPIRED autopilot marker. Returns the names removed.

    ADR-001 turned one file into N and gave each one a self-only reaper (`gc_stale_marker`,
    ADR-013), which collects a marker only when its OWN session next runs a command — and a
    crashed session never does. Nothing else globbed, so `.claude/` grew a file per session
    forever (review round 1, SR-3; `gc_stale_marker`'s docstring claiming a peer's marker
    "survives to its TTL" described a sweep that did not exist).

    ADR-013 scopes a **session's** unlink authority, not the operator's: `prune_stale` is
    already the session-blind sweep that owns `.hm-loop-*` and `.hm-task-*`, and this joins
    them. **TTL-expired only** — `stale`, never `fresh` and never `future`, so a live peer's
    marker and a clock-skewed one are both untouchable, which is the property ADR-013's
    restraint actually protects.
    """
    claude_dir = project_root / _MARKER_DIR
    if not claude_dir.is_dir():
        return []
    removed: list[str] = []
    for path in sorted(claude_dir.glob(f"{_MARKER_BASENAME}*")):
        try:
            raw = path.read_bytes()
            marker = AutopilotMarker.model_validate(json.loads(raw.decode("utf-8")), strict=False)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            continue  # unparseable: the OWNER's gc_stale_marker collects it; never guess here
        if _freshness(marker.created_at) != "stale":
            continue
        try:
            if path.read_bytes() != raw:  # CAS, same reason as gc_stale_marker
                continue
            path.unlink()
        except OSError:
            continue
        removed.append(path.name)
    return removed


def idle_minutes(marker: AutopilotMarker, *, now: datetime | None = None) -> float | None:
    """Minutes since the owner last touched the marker; None when it cannot be known.

    Falls back to ``created_at`` so a marker written before this field existed still yields
    a number rather than an unknown.

    A stamp in the FUTURE returns None, not 0.0. Clamping it to zero reported "active right
    now" for a clock-skewed marker — and the picker puts this number to the user as the fact
    that settles whether to take the marker over, so a skewed peer marker (which is also
    protected from GC and from overwrite while the skew is under one TTL) would keep the
    project gated for the full window on a number that is not evidence of anything.
    """
    stamp = marker.last_seen or marker.created_at
    moment = now if now is not None else datetime.now(UTC)
    try:
        seen = datetime.fromisoformat(stamp)
    except (ValueError, TypeError, OverflowError):
        return None
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    elapsed = (moment - seen).total_seconds() / 60.0
    return None if elapsed < 0 else elapsed


def _write_if_unchanged(
    root: Path, *, before: bytes | None, updated: AutopilotMarker, session_id: str | None
) -> bool:
    """Write ``updated`` only if the marker file still holds ``before``. False otherwise.

    Byte identity, NOT a `created_at` comparison. Neither `touch` nor `set_task_slug`
    mutates `created_at` — `touch` changes `last_seen`, `set_task_slug` changes
    `task_slug` — so a `created_at` check passes for every SAME-OWNER collision and each
    writer silently reverts the other's field. That population is real: `_is_own` falls
    back to the project-scoped `session_uuid` whenever neither side has a session id, so
    every id-less session (Cursor, Codex, a WSL2 env-file failure) co-owns one marker.
    Reverting a just-written `task_slug` points the next stage at another task; reverting
    `last_seen` inflates `idle_minutes`, the number the picker uses to authorize a
    takeover. `gc_stale_marker` already used byte identity for the same reason.
    """
    path = marker_path(root, session_id=session_id)
    try:
        if path.read_bytes() != before:
            logger.warning(".hm-autopilot: marker changed during update — skipping write.")
            return False
        atomic_write(path, updated.model_dump_json())
    except OSError:
        return False
    return True


def touch(project_root: Path, *, now: str | None = None, session_id: str | None = None) -> bool:
    """Refresh ``last_seen`` iff this session owns the ACTIVE marker. Best-effort.

    Gated on ``active_marker`` so a peer can never advance someone else's heartbeat and
    keep their marker looking live. Any write failure is swallowed: a missed heartbeat
    degrades the takeover prompt's wording, it must never break a stage.

    ``session_id`` must be threaded from the caller for the same reason every other
    marker reader takes it (ADR-001): once the picker stamps an id, an id-less resolve
    here is foreign to the marker this very session wrote, so the heartbeat becomes a
    permanent silent no-op and a live owner looks abandoned to the takeover prompt.
    """
    root = resolve_marker_root(project_root)
    # Before the read: an ADR-003 project's only marker is still at the legacy path, so
    # without the migration `before` is None and the heartbeat is a permanent no-op.
    _takeover_legacy(root, session_id=session_id)
    try:
        before: bytes | None = marker_path(root, session_id=session_id).read_bytes()
    except OSError:
        return False
    marker = active_marker(root, session_id=session_id)
    if marker is None:
        return False
    stamped = marker.model_copy(
        update={"last_seen": now if now is not None else datetime.now(UTC).isoformat()}
    )
    return _write_if_unchanged(root, before=before, updated=stamped, session_id=session_id)


def set_task_slug(
    project_root: Path, *, slug: str, stage: str, session_id: str | None = None
) -> bool:
    """Persist the task slug onto the ACTIVE marker. False when this session owns none.

    Gated on ``active_marker`` rather than ``load`` so a foreign marker is never
    slug-written — that read-modify-write is the only remaining marker-clobber window
    (R9), and refusing outright closes it for every non-owner.

    ``session_id`` is threaded for the ADR-001 reason: an id-less resolve against an
    id-stamped marker returns None here, and the caller turns that False into a
    ``bad_slug`` halt naming a slug that in fact passed validation.
    """
    root = resolve_marker_root(project_root)
    _takeover_legacy(root, session_id=session_id)
    try:
        before: bytes | None = marker_path(root, session_id=session_id).read_bytes()
    except OSError:
        return False
    marker = active_marker(root, session_id=session_id)
    if marker is None:
        return False
    try:
        # `model_copy(update=...)` does NOT re-run validators, so the charset allowlist on
        # `task_slug` would be bypassed on this path — the one that actually persists a
        # model-supplied value. Re-validate explicitly.
        updated = AutopilotMarker.model_validate(
            {**marker.model_dump(), "task_slug": slug, "task_slug_stage": stage}, strict=False
        )
    except ValidationError:
        logger.warning(".hm-autopilot: rejected task_slug %r — marker left unchanged.", slug)
        return False
    return _write_if_unchanged(root, before=before, updated=updated, session_id=session_id)


def active_marker(
    project_root: Path, *, now: datetime | None = None, session_id: str | None = None
) -> AutopilotMarker | None:
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
    marker = load(project_root, session_id=session_id)
    if marker is None:
        return None
    if not _is_own(marker, project_root, session_id=session_id or None):
        logger.warning(".hm-autopilot: marker belongs to another session (foreign) — ignoring.")
        return None
    # Rejects everything that is not `fresh` — a too-old marker (crash leftover) AND a
    # future-dated one (clock skew, or a crafted created_at that would otherwise keep
    # autopilot armed forever — a negative age slips past a one-sided `> TTL` check).
    # REVIEW round-2 P2. Rejection is non-destructive; only `stale` is ever deletable
    # (gc_stale_marker).
    if _freshness(marker.created_at, now) != "fresh":
        logger.warning(".hm-autopilot: marker outside the freshness window — ignoring.")
        return None
    return marker


_VALID_LEVELS = frozenset({"gated", "auto_safe", "full"})


def effective_level(project_root: Path, *, yaml_level: str, session_id: str | None = None) -> str:
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
    marker = active_marker(project_root, session_id=session_id)
    if marker is not None:
        return marker.level
    if yaml_level not in _VALID_LEVELS:
        logger.warning(".hm-autopilot: unknown yaml autonomy.level %r → gated.", yaml_level)
        return "gated"
    return yaml_level


def status(project_root: Path, *, session_id: str | None = None) -> dict[str, Any]:
    """The deterministic answer to "is autopilot active?" (ADR-002).

    ``session_id`` is this caller's own id, supplied explicitly because it CANNOT be read
    from the environment: `sessionid_envfile` writes `HM_SESSION_ID` into
    `$CLAUDE_ENV_FILE`, which Claude Code sources as an unexported shell variable, so
    `os.environ` never sees it (PLAN-sessionid-env-propagation ADR-001/005). Empty string
    means id-less here — unlike the readiness tri-state, this path deliberately collapses
    `""` and `None`, because the rendered call sites pass the flag unconditionally and
    Cursor/Codex/degraded sessions legitimately deliver an empty value.

    This exists because the picker had no way to ask. Its arm condition — "if no marker
    is active yet" — had only `on`/`off` behind it, so the model fell back to checking
    whether the FILE exists; a stale marker then suppressed arming indefinitely, since
    nothing ever deleted it. That is the dominant path by which autopilot goes dark.

    `reason` is load-bearing, not diagnostic: `active: false` alone would send the picker
    down the arming branch for a foreign marker and clobber a live peer (ADR-010).

    GC runs FIRST so a crashed peer's stale marker is collected even though it is foreign;
    its failure is suppressed and reported — an uncaught OSError would leave the picker
    with no JSON to branch on, re-entering the exact guess-at-the-file failure this
    command removes.
    """
    root = resolve_marker_root(project_root)
    effective_id = session_id or _env_session_id()
    out: dict[str, Any] = {
        "active": False,
        "reason": "absent",
        "level": None,
        "pipeline": None,
        "task_slug": None,
        "session_scoped": False,
        "idle_minutes": None,
    }
    # BEFORE the existence check: an ADR-003 project's marker is still at the legacy
    # path, and reporting "absent" there would send the picker down the arming branch
    # for a project that is already armed.
    _takeover_legacy(root, session_id=effective_id)
    if not marker_path(root, session_id=effective_id).is_file():
        # ADR-001 made "some OTHER session's marker exists" a non-event for an id-bearing
        # caller: its own path is free, so it arms. But an id-LESS caller cannot tell
        # "nobody armed" from "I armed, and then lost my id" — the documented WSL2 shape
        # where `sessionid_envfile` fails while the SessionStart hook still stamps the id
        # it read from stdin. Report that distinctly (read-only; ADR-013 restricts
        # unlinking, not looking) so the degraded environment is diagnosable instead of
        # silently arming a second, parallel marker with no explanation.
        if effective_id is None:
            peer = _some_id_bearing_marker(root)
            if peer is not None:
                out["reason"] = "degraded-idless"
                out["idle_minutes"] = idle_minutes(peer)
        return out
    try:
        if gc_stale_marker(root, session_id=effective_id):
            out["reason"] = "stale (gc'd)"
            return out
    except OSError as exc:
        out["reason"] = f"gc-failed: {exc.errno if exc.errno is not None else '?'}"
        return out
    marker = load(root, session_id=effective_id)
    if marker is None:
        # Unparseable survived GC only if the file vanished underneath us.
        out["reason"] = "absent"
        return out
    if not _is_own(marker, root, session_id=effective_id):
        # A caller with NO id of its own cannot tell "a peer owns this" from "this is mine
        # and I lost my id". Those need opposite advice, so they get different labels.
        #
        # The id-less case is a real, documented environment, not a corner: on WSL2 the
        # `sessionid_envfile` publish to `$CLAUDE_ENV_FILE` can fail, and then the
        # SessionStart hook still receives the id on stdin (so the marker IS stamped) while
        # this session's Bash has none. Reporting that as `foreign` tells the picker a live
        # peer owns the user's own marker — and ADR-010's branch then refuses to arm, so
        # autopilot stays dark for the full TTL with no in-band recovery. That is the same
        # advance-noop class this whole change exists to remove, relocated.
        out["reason"] = (
            "degraded-idless"
            if effective_id is None and marker.claude_session_id is not None
            else "foreign"
        )
        # Neither reason authorizes a takeover on its own — this is how long the owner has
        # been silent, so the picker can state a FACT and let the user (the only party who
        # knows whether another session is open) decide. Round 4 found the alternative:
        # prose asserting "probably yours" told the agent to `--force` over what may be a
        # live peer.
        out["idle_minutes"] = idle_minutes(marker)
        return out
    fresh = _freshness(marker.created_at)
    if fresh != "fresh":
        out["reason"] = "future-dated" if fresh == "future" else "stale (gc'd)"
        return out
    out.update(
        active=True,
        reason="armed",
        level=marker.level,
        pipeline=[s.value for s in marker.pipeline],
        task_slug=marker.task_slug,
        session_scoped=effective_id is not None and marker.claude_session_id is not None,
    )
    return out


def _cli_off(
    project_root: Path, *, session_id: str | None, emit: Callable[[str, bool], None]
) -> int:
    """Shared `autopilot off` behavior for BOTH entry points. Returns the exit code.

    Shared for the same reason `resolve_toggle_config` is: the Typer alias and the dot-form
    are one command with two spellings, and the last time only one was updated the other
    surfaced a raw traceback.

    **`off` DISARMS THE PROJECT, not just the caller's key.** ADR-013 scopes a *session's*
    unlink authority so no peer can silently disarm another; an operator typing the README's
    kill switch is not a peer. Two rounds of review landed on this: keying `off` to the
    caller made it a silent no-op on its only documented invocation (there is no
    `--session-id` in the README, and `HM_SESSION_ID` is a shell variable `os.environ` never
    sees), and merely reporting that honestly still left the chain auto-advancing for the
    full 18h TTL with manual file deletion as the only working disarm. A kill switch that
    cannot kill is the defect; telling the truth about it is not the fix.

    With `--session-id`, only that session's marker is removed — the scoped form stays
    available for a stage that means "disarm ME".
    """
    removed = (
        [marker_path(project_root, session_id=session_id).name]
        if clear(project_root, session_id=session_id)
        else []
    )
    root = resolve_marker_root(project_root)
    if session_id is None:
        # Operator sweep: every remaining keyed marker in this project, TTL or not.
        for name in other_keyed_markers(root, session_id=session_id):
            try:
                (root / _MARKER_DIR / name).unlink(missing_ok=True)
            except OSError as exc:
                emit(f"autopilot: could not remove {name}: {exc}", True)
                return 4
            removed.append(name)
    if removed:
        emit(
            f"autopilot: off ({len(removed)} marker(s) cleared: {', '.join(sorted(removed))})",
            False,
        )
        return 0
    stranded = other_keyed_markers(root, session_id=session_id)
    if not stranded:
        emit("autopilot: off (no marker was armed)", False)
        return 0
    # Only reachable with an explicit --session-id that owns nothing while peers are armed.
    emit(
        f"autopilot: this session owns no marker; {len(stranded)} other marker(s) are still "
        f"armed: {', '.join(stranded)}. Re-run without --session-id to disarm the project.",
        True,
    )
    return 4


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
    parser.add_argument("action", choices=["on", "off", "status"])
    parser.add_argument("--level", default="auto_safe")
    parser.add_argument("--pipeline", default=None)
    parser.add_argument("--root", default=None)
    # ADR-010: taking over a live peer's marker must be deliberate, never a side effect
    # of the picker offering to arm.
    parser.add_argument("--force", action="store_true")
    # PLAN-sessionid-env-propagation ADR-005: the id cannot be read from the process
    # environment (the SessionStart hook publishes it as an UNEXPORTED shell variable),
    # so the rendered picker passes it explicitly. Writer and readers must agree — a
    # marker stamped with an id that the boundary readers cannot match is kill_switch.
    parser.add_argument("--session-id", default=None, dest="session_id")
    args = parser.parse_args(raw)
    root = Path(args.root) if args.root else Path.cwd()
    if args.action == "status":
        print(json.dumps(status(root, session_id=args.session_id)))
        return 0
    if args.action == "off":

        def _emit(message: str, err: bool) -> None:
            print(message, file=sys.stderr if err else sys.stdout)

        return _cli_off(root, session_id=args.session_id, emit=_emit)
    try:
        level, stages = resolve_toggle_config(args.level, args.pipeline)
    except ValueError as exc:
        print(f"autopilot: {exc}", file=sys.stderr)
        return 2
    try:
        marker = write(
            root,
            level=level,
            pipeline=stages,
            force=args.force,
            claude_session_id=args.session_id or None,
        )
    except MarkerOwnedByAnotherSessionError as exc:
        print(f"autopilot: {exc}", file=sys.stderr)
        return 3
    except ValidationError as exc:
        print(f"autopilot: invalid config ({exc})", file=sys.stderr)
        return 2
    print(f"autopilot: on (level={marker.level}, {len(marker.pipeline)} stages)")
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main(argv) in tests
    sys.exit(main())
