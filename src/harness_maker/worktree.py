"""Git worktree lifecycle (Phase 8 / Task 8.1).

Provides create / cleanup / merge / cleanup_all primitives used by the
worktree-isolator skill and by the autoloop driver. All git invocations go
through subprocess.run with check=True; CalledProcessError is caught and
re-raised as RuntimeError with the captured stderr to keep failure modes
explicit and observable.

Conventions
-----------
- Worktree path:  <base>/.worktrees/<workflow>-<UTC-ISO8601-minute>
- Branch name:    same basename as the worktree directory ("hm-" prefix optional;
                  the harness.yaml worktree.branch_prefix surfaces only in skill
                  prose for now — Phase 9 will adopt it here).
- Time precision: minutes (YYYYmmddTHHMMZ) — collisions inside the same minute
                  are extremely unlikely for a single-user CLI, and longer suffixes
                  hurt path readability.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import yaml

from harness_maker import command_registry
from harness_maker.io_utils import atomic_write, load_harness_yaml

# Used by both stash list SHA capture and ref-file validation (ADR-002).
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# Anchors the session_marker absolute-path regex (ADR-002): leading `/`,
# followed by some directory chain, then `/.claude/.hm-loop-<wt-name>`.
_SESSION_MARKER_RE = re.compile(r"^/.+/\.claude/\.hm-loop-[A-Za-z0-9_.-]+$")

WORKTREE_DIR_NAME = ".worktrees"
_TASK_BRANCH_PREFIX = "hm/"  # per-task feature-branch spine (ADR-002)
_TS_FMT = "%Y%m%dT%H%MZ"
_GIT_TIMEOUT = 60  # seconds — prevent hang on SSH prompt or NFS stall
# Longer timeout for `git stash push -u` on large working trees with untracked
# binary artifacts. Bumped per REVIEW M-P1-3 — 60s was tight for repos >100MB.
_GIT_TIMEOUT_LONG = 300
# Merge-fence acquire-timeout (PLAN-p6-p7-worktree-finalize CN1, supersedes
# ADR-003's "keep 60s"). The fenced critical section now HOLDS the lock for up
# to _GIT_TIMEOUT_LONG (the stash) + _GIT_TIMEOUT (the merge); a waiter's
# acquire budget must exceed that worst-case hold, else a legitimately-slow
# first finalize spuriously times out a parallel second one.
_FENCE_TIMEOUT = _GIT_TIMEOUT_LONG + _GIT_TIMEOUT  # 360s
# O_EXCL stale-lock reap threshold (PLAN-multisession-10-fleet-hardening ADR-003).
# Only an UNPARSEABLE/legacy lock body is age-reaped; a live holder is NEVER
# reaped by age (the fence acquire-timeout bounds waiting, not hold time, so a
# slow/hung-but-live land legitimately holds past this). 2× the fence budget
# comfortably exceeds any legitimate hold.
_EXCL_STALE_AGE = 2 * _FENCE_TIMEOUT  # 720s
# Pre-create reservation / prune grace (PLAN-worktree-prune-create-race ADR-001/002).
# A peer's in-flight `create()` writes `.hm-creating-<name>` BEFORE `git worktree
# add`; a reservation fresher than this is honored (the dir is protected from a
# concurrent prune). Generous — must exceed a `git worktree add` + checkout +
# post-checkout hooks, NOT coupled to `_GIT_TIMEOUT` (Codex: no margin there).
_PRUNE_GRACE_SECONDS = 300
_RESERVATION_GITIGNORE_PATTERN = ".claude/.hm-creating-*"

# Per-session marker files: .claude/.hm-loop-{primary-wt-basename}
# One file per active session — parallel sessions coexist without collision.
# Gate reads all matching files via glob. Finalize deletes only its own file.
_LOOP_MARKER_DIR = Path(".claude")
_LOOP_MARKER_PREFIX = ".hm-loop-"
_LOOP_MARKER_GITIGNORE_PATTERN = ".claude/.hm-loop-*"

# PLAN-worktree-base-artifact-pollution ADR-002/ADR-003: single source of
# truth for harness-generated CHURN paths. The gitignore set AND both
# dirt-filters derive from these tuples so they cannot drift. These are
# regenerable per-session artifacts — they must neither block `worktree
# create` (dirty-base guard) nor trigger a finalize stash. Deliverables
# (work-docs/{PLAN,REVIEW,RESEARCH,SPEC}, specs/, human memory tiers
# wiki.md/failures.md/session/) are deliberately EXCLUDED so wrapup can
# still commit them. Each entry doubles as a valid .gitignore pattern.
#
# Directory churn — matched by prefix (`startswith`); the trailing slash makes
# the match unambiguous (`.claude/memory/semantic/` cannot collide with a
# sibling like `.claude/memory/semantic-notes.md`).
_HARNESS_CHURN_DIRS: tuple[str, ...] = (
    ".claude/observability/",
    ".claude/.hm-iter-receipts/",
    ".claude/loop-specs/",
    ".claude/memory/semantic/",
    ".claude/memory/episodic/",
    ".claude/memory/profile/",
    "work-docs/loop-context/",
)
# File churn — matched EXACTLY (`==`), not by prefix, so a coincidental sibling
# like `work-docs/p5-batch-state.yaml.bak` is NOT wrongly forgiven (REVIEW
# consensus: code + security reviewers).
#
# Known limitation (REVIEW): the two `work-docs/` entries assume the default
# `work_docs.dir` ("work-docs/"). A non-default `work_docs.dir` is not covered
# by churn-isolation — these filters are pure porcelain-line predicates with no
# harness.yaml access. The dominant churn (`.claude/observability/`, written on
# every tool call) is NOT configurable, so the core fix holds regardless.
_HARNESS_CHURN_FILES: tuple[str, ...] = (
    ".claude/.hm-session-uuid",
    ".claude/.hm-autopilot",
    ".claude/.hm-render-manifest.jsonl",
    ".claude/.hm-sessions.json",  # Phase 1 (ADR-004): session registry — operational churn
    "work-docs/p5-batch-state.yaml",
)
# Glob patterns that are prefix-keyed (not exact files and not dir-prefixes).
# These are gitignore-only entries — they appear in .gitignore but the dirt filter
# handles them via the corresponding prefix in `_HARNESS_ARTIFACT_PREFIXES` instead.
# PLAN-spec-requirement-gate ADR-009: `.hm-spec-need-{slug}` markers are slug-keyed
# and therefore cannot be an exact-file or dir-prefix entry.
_HARNESS_CHURN_GLOBS: tuple[str, ...] = (".claude/.hm-spec-need-*",)
# Patterns appended to the user's .gitignore (ADR-002) — dirs + exact files + globs.
# The Phase 2 sync test asserts this equals the dir+file+glob union so the gitignore
# set and the dirt-filters can never drift.
_HARNESS_GITIGNORE_PATTERNS: tuple[str, ...] = (
    _HARNESS_CHURN_DIRS + _HARNESS_CHURN_FILES + _HARNESS_CHURN_GLOBS
)

# PLAN-worktree-deliverable-blocks-create ADR-001: harness deliverable docs.
# `/hm:plan` writes these to `work-docs/` (and `specs/`) BEFORE `/hm:execute`,
# and they are excluded from the churn set above so `/hm:wrapup` can commit them
# — so they are ALWAYS uncommitted at `worktree create` time and would block
# every plan→execute. Anchored FULL-MATCH (mirrors the EXACT-match churn-file
# discipline) so siblings like `PLAN-x.md.bak` / `random.md` are NOT forgiven.
# NON-GOAL: a non-default harness.yaml `work_docs.dir` is not covered — same
# accepted limitation as the churn-filter (pure porcelain predicate, no
# harness.yaml access).
# `[^/]+` (not `.+`) so the match is a FLAT file — a nested user dir like
# `work-docs/PLAN-experiments/notes.md` must NOT be forgiven (anti-over-match;
# `/hm:plan` only ever writes deliverables flat, so no real coverage is lost).
_DELIVERABLE_RE = re.compile(
    r"^(?:work-docs/(?:PLAN|RESEARCH|SPEC|REVIEW)-[^/]+\.md|specs/SPEC-[^/]+\.md)$"
)


def _is_deliverable_path(path: str) -> bool:
    """True iff path is a harness deliverable doc (anchored full-match).

    The create-guard forgives these per-line; the finalize filter
    (`_is_harness_artifact`) does NOT, so they stay stash-preserved.
    """
    return bool(_DELIVERABLE_RE.match(path))


def _run(
    args: list[str], cwd: Path, timeout: int | None = None
) -> subprocess.CompletedProcess[str]:
    """Wrap subprocess.run with check=True + capture; uniform error surface.

    The optional ``timeout`` parameter overrides the default ``_GIT_TIMEOUT``
    for individual call sites that need more time (e.g., ``git stash push -u``
    on a large working tree).
    """
    effective_timeout = _GIT_TIMEOUT if timeout is None else timeout
    try:
        return subprocess.run(  # noqa: S603 — args list, no shell
            args,
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
        )
    except subprocess.CalledProcessError as e:
        msg = (
            f"git command failed (exit {e.returncode}): {' '.join(args)}\n"
            f"stderr: {e.stderr.strip() if e.stderr else '<empty>'}"
        )
        raise RuntimeError(msg) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"git command timed out after {effective_timeout}s: {' '.join(args)}"
        ) from e


def _timestamp() -> str:
    """UTC ISO8601 minute-precision suffix (filesystem-safe)."""
    return datetime.now(UTC).strftime(_TS_FMT)


# PLAN-worktree-cross-session-data-loss-defense ADR-004 §2 (dirname UUID embed)
# Worktree dirname now `<workflow>-<uuid12>-<ts>`. Old format `<workflow>-<ts>`
# remains parseable for back-compat (returns empty UUID — caller treats as
# "not owned" which is the safe default for cross-session pop checks).
_WT_NAME_RE = re.compile(
    r"^(?P<workflow>[a-z][a-z0-9-]*?)"
    r"(?:-(?P<uuid>[0-9a-f]{12}))?"
    r"-(?P<ts>\d{8}T\d{4}Z)"
    r"(?:-(?P<dedup>\d+))?$"
)


def _extract_uuid_from_wt_name(name: str) -> str:
    """Parse 12-hex UUID from worktree dirname `<workflow>-<uuid>-<ts>`.

    Returns empty string when:
    - the name is in legacy `<workflow>-<ts>` format (no UUID embedded), OR
    - the name doesn't match the expected schema at all.

    PLAN-worktree-cross-session-data-loss-defense ADR-004 §2: UUID-in-dirname
    is the durable create→finalize→pop binding. Replaces the broken
    `_current_session_uuid` persistent-file approach (REVIEW round 1
    P0-MAN2 — that helper returned shared per-project UUID, defeating
    cross-session isolation).
    """
    if not name:
        return ""
    m = _WT_NAME_RE.match(name)
    if m is None:
        return ""
    return m.group("uuid") or ""


_OWNED_CRUMB_GITIGNORE_PATTERN = ".claude/.hm-owned-uuids-*"


def _owned_crumb_path(base: Path, slug: str) -> Path:
    """Slug-keyed crumb recording the uuid(s) a session deferred for ``<slug>``.

    PLAN-layer3-per-session-ownership ADR-001: a machine-derived owned set that
    survives the execute→wrapup boundary — a standalone/recovered wrapup reads it
    by its own ``<slug>`` arg with no conversation memory. **Distinct-slug peers
    never share** an owned set — that is the fleet-isolation guarantee this closes.

    SCOPE LIMIT (REVIEW P1 — do NOT believe "fail-safe for same-slug"): the crumb
    is keyed by SLUG, not session, and ``_owned_crumb_add`` UNIONs uuids. So TWO
    DIFFERENT sessions both working the SAME ``<slug>`` accumulate both uuids into
    one crumb, and the first wrapup then pops the OTHER session's still-live
    deferred stash — a peer-pop, not a strand. This is the same-task concurrency
    footgun: flag-ON blocks it (``claim_task_branch`` ``SharedSlugError``); flag-OFF
    relies on single-session-per-slug discipline (two sessions on one slug already
    share the ``.worktrees/<…>`` namespace). It is no worse than the pre-fix
    all-markers behavior (which popped peers regardless of slug); a proper fix needs
    a SharedSlug guard on this flag-off crumb path (follow-up). The empty-string slug
    is rejected at the CLI to stop a missed substitution from sharing one crumb
    across UNRELATED tasks.
    """
    safe = re.sub(r"[^A-Za-z0-9_.-]", "-", slug)
    return base / _LOOP_MARKER_DIR / f".hm-owned-uuids-{safe}"


def _owned_crumb_read(base: Path, slug: str) -> list[str]:
    """Return the recorded uuids for ``<slug>`` (sorted, deduped); ``[]`` if absent."""
    try:
        text = _owned_crumb_path(base, slug).read_text(encoding="utf-8")
    except OSError:
        return []
    return sorted({ln.strip() for ln in text.splitlines() if ln.strip()})


def _owned_crumb_add(base: Path, slug: str, uuid_str: str) -> None:
    """Idempotently append ``uuid_str`` to the slug crumb (atomic + gitignored)."""
    from harness_maker.io_utils import atomic_write

    if not uuid_str:
        return
    owned = set(_owned_crumb_read(base, slug))
    owned.add(uuid_str)
    atomic_write(_owned_crumb_path(base, slug), "\n".join(sorted(owned)) + "\n")
    _ensure_gitignore_entry(base, _OWNED_CRUMB_GITIGNORE_PATTERN)


def _owned_crumb_clear(base: Path, slug: str) -> None:
    """Remove the slug crumb after a successful pop (idempotent)."""
    _owned_crumb_path(base, slug).unlink(missing_ok=True)


def _owned_session_uuids(base: Path) -> set[str]:
    """Return the set of UUIDs for worktrees currently owned by THIS process.

    Source: `.claude/.hm-loop-{wt-name}` marker files at base — each one
    represents an active session's worktree. UUID extracted from the
    `{wt-name}` portion of the filename. Empty UUIDs (legacy wt names)
    are excluded — they can't participate in UUID-based ownership.

    This replaces the broken `_current_session_uuid(base)` which returned
    a single shared per-project value. With dirname UUIDs, each active
    session contributes a distinct UUID and post-commit-pop can match
    refs against the live owned-set.
    """
    claude_dir = base / _LOOP_MARKER_DIR
    if not claude_dir.is_dir():
        return set()
    owned: set[str] = set()
    for marker_path in claude_dir.glob(f"{_LOOP_MARKER_PREFIX}*"):
        wt_name = marker_path.name[len(_LOOP_MARKER_PREFIX) :]
        uuid_str = _extract_uuid_from_wt_name(wt_name)
        if uuid_str:
            owned.add(uuid_str)
    return owned


def _current_branch(repo: Path) -> str:
    """Return the current branch name of repo (HEAD's symbolic ref)."""
    cp = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    return cp.stdout.strip()


def _branch_exists(repo: Path, name: str) -> bool:
    """Return True if a branch with this name exists in repo."""
    cp = _run(["git", "branch", "--list", name], cwd=repo)
    return bool(cp.stdout.strip())


def _find_free_name(
    workflow: str,
    ts: str,
    primary: Path,
    sibling_dirs: list[Path],
    sibling_slugs: list[str],
) -> str:
    """Find a base name whose derived branch names are free in ALL repos.

    Primary branch = ``{name}``.
    Sibling branch  = ``{name}-{slug}``.
    Checks all repos before committing to any git worktree add.

    PLAN-worktree-cross-session-data-loss-defense ADR-004 §2: `ts` is now
    expected to be the `{uuid12}-{ts}` combo when caller wants UUID embed
    (callers pass it via `ts=f"{uuid}-{timestamp_str}"`). Pure timestamp
    is still accepted for back-compat with tests that don't care about
    cross-session isolation.
    """
    base_name = f"{workflow}-{ts}"
    for attempt in range(100):
        name = base_name if attempt == 0 else f"{base_name}-{attempt}"
        if _branch_exists(primary, name):
            continue
        if any(
            _branch_exists(sibling, f"{name}-{slug}")
            for sibling, slug in zip(sibling_dirs, sibling_slugs, strict=True)
        ):
            continue
        return name
    raise RuntimeError(f"No free branch name found after 100 attempts with prefix {base_name!r}")


def create(
    workflow: str,
    base_dir: Path,
    sibling_dirs: list[Path] | None = None,
    claude_session_id: str = "",
) -> list[Path]:
    """Create git worktrees for primary and optional sibling repos.

    Returns [primary_wt, *sibling_wts]. Single-repo → list of length 1.
    Branch names: primary={name}, sibling={name}-{slug} where slug=sibling.name.

    Pre-flights branch-name availability across ALL repos before creating any,
    so a collision in repo N does not leave repos 0..N-1 with orphan worktrees.
    """
    base = base_dir.resolve()
    siblings = [s.resolve() for s in (sibling_dirs or [])]
    slugs = [s.name for s in siblings]

    # PLAN-worktree-cross-session-data-loss-defense ADR-004 §2 (dirname
    # UUID embed). 12-hex UUID generated at create-time, embedded between
    # workflow + timestamp in the wt name. post-commit-pop reads the
    # UUID set from active .hm-loop-* marker filenames (the set of
    # currently-owned worktrees) and matches ref-files against that set.
    # Refs whose session_uuid is NOT in the owned set → skip (cross-session
    # contamination blocked). 48 bits of entropy is sufficient for
    # collision-avoidance among concurrent local sessions.
    session_uuid = uuid.uuid4().hex[:12]
    ts = f"{session_uuid}-{_timestamp()}"
    name = _find_free_name(workflow, ts, base, siblings, slugs)

    # Create primary worktree
    (base / WORKTREE_DIR_NAME).mkdir(parents=True, exist_ok=True)
    primary_wt = base / WORKTREE_DIR_NAME / name
    # ADR-001 (prune-create race): reserve the primary leaf BEFORE git creates it,
    # so a concurrent `prune_stale` never rmtrees the in-flight dir. The outer
    # try/finally MUST span the primary add through the marker write (the exact
    # window the prune scan races) and remove the reservation on every exit.
    reservation = _reservation_path(base, name)
    _ensure_gitignore_entry(base, _RESERVATION_GITIGNORE_PATTERN)
    atomic_write(reservation, f"{session_uuid}\n")
    try:
        _run(["git", "worktree", "add", "-b", name, str(primary_wt)], cwd=base)

        # Create sibling worktrees
        sibling_wts: list[Path] = []
        try:
            for sibling, slug in zip(siblings, slugs, strict=True):
                sib_name = f"{name}-{slug}"
                (sibling / WORKTREE_DIR_NAME).mkdir(parents=True, exist_ok=True)
                sib_wt = sibling / WORKTREE_DIR_NAME / sib_name
                _run(["git", "worktree", "add", "-b", sib_name, str(sib_wt)], cwd=sibling)
                sibling_wts.append(sib_wt)
        except RuntimeError:
            # Rollback: remove all already-created worktrees (including primary) so
            # no orphaned git worktrees accumulate without a marker or cleanup path.
            for created_wt, sib in zip(sibling_wts, siblings[: len(sibling_wts)], strict=False):
                with contextlib.suppress(RuntimeError):
                    _run(["git", "worktree", "remove", "--force", str(created_wt)], cwd=sib)
            with contextlib.suppress(RuntimeError):
                _run(["git", "worktree", "remove", "--force", str(primary_wt)], cwd=base)
            raise

        all_wts = [primary_wt, *sibling_wts]
        _write_loop_marker(base, primary_wt.name, all_wts, claude_session_id=claude_session_id)
        return all_wts
    finally:
        reservation.unlink(missing_ok=True)


def cleanup(wt_path: Path, on_success: bool) -> None:
    """Remove the given worktree.

    On success: force removal (drop the branch's working copy unconditionally).
    On failure: non-force removal — preserves uncommitted work for inspection
    (git will error if the worktree is dirty, which is the desired safety net).
    """
    wt = wt_path.resolve()
    # Repo root = parent of `.worktrees/<name>`
    base = wt.parent.parent
    args = ["git", "worktree", "remove"]
    if on_success:
        args.append("--force")
    args.append(str(wt))
    try:
        _run(args, cwd=base)
    except RuntimeError:
        # Failure-path cleanup is best-effort: if removal fails (e.g. dirty
        # worktree on the failure branch), leave the directory for the user
        # rather than masking the original error.
        if on_success:
            raise


def _capture_pending_in_worktree(wt_path: Path) -> bool:
    """Auto-commit uncommitted work inside the worktree before merge runs.

    Without this step, ``git merge --squash <branch>`` from the base repo only
    sees commits on <branch>. If the worktree has staged or unstaged edits that
    were never committed, ``cleanup(force=True)`` deletes them — silent data loss.

    Returns True when a WIP commit was created, False when the worktree was
    already clean.

    On commit failure (e.g., pre-commit hook rejection, .git/index.lock
    contention with a Cursor co-writer), the staged state is rolled back via
    ``git reset HEAD`` so the worktree is left in a consistent state for retry.

    Known limitation: the status-check + add + commit sequence is not atomic
    against a concurrent writer (e.g., Cursor IDE editing the same worktree).
    On the OLD/legacy teardown path, cleanup --force may delete a Cursor write
    that arrived after our status check but before our git add — that loss
    vector is teardown-specific. On the ADR-007 commit-not-stash path the
    caller never tears the worktree down and re-checks `_worktree_is_dirty`
    after this returns, so a late write is non-destructive (it stays in the
    worktree and forces `rc=1` rather than a false success). CLAUDE.md
    "Worktree 공유" notes the prefix-match cleanup boundary; in practice
    harness-maker and Cursor own different worktree prefixes, so the actual
    race surface is small.
    """
    wt = wt_path.resolve()
    status = _run(["git", "status", "--porcelain"], cwd=wt)
    if not status.stdout.strip():
        return False
    branch = wt.name
    _run(["git", "add", "-A"], cwd=wt)
    try:
        _run(
            [
                "git",
                "commit",
                "-m",
                f"wip(execute): capture uncommitted work in worktree {branch}",
                "--no-verify",
            ],
            cwd=wt,
        )
    except RuntimeError:
        # Roll back the staging so the next finalize attempt sees the original state.
        try:
            _run(["git", "reset", "HEAD"], cwd=wt)
        except RuntimeError as reset_err:
            print(
                f"[finalize] reset rollback also failed: {reset_err}",
                file=sys.stderr,
            )
        raise
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Base-side stash isolation envelope (PLAN-worktree-finalize-stash-isolation).
#
# Before squash-merging the worktree branch into base, stash any pre-existing
# dirty work in base (tracked + staged + untracked). After the merge completes,
# pop the stash so the user's unrelated work is restored — collapsed to
# unstaged per ADR-001 §3 (accepted trade-off; alternative `--keep-index`
# exposes staged content to squash, creating a different silent corruption).
# ──────────────────────────────────────────────────────────────────────────────

_STASH_MESSAGE_PREFIX = "hm-finalize-"

# Substrings consumers (Step 5 LLM contract, ADR-003) literal-match for the
# autoloop AskUserQuestion exception. Keep stable — changing breaks the gate.
_POP_CONFLICT_SIGNAL = "[finalize] stash-pop conflict — autoloop must halt"
_UNTRACKED_COLLISION_SIGNAL = "[finalize] untracked-file collision — autoloop must halt"
_POP_UNKNOWN_SIGNAL = "[finalize] stash-pop failed (class=unknown) — autoloop must halt"


def _probe_submodules(base: Path) -> None:
    """ADR-005: abort if any submodule has dirty pointer or uninit state.

    `git submodule status` prefixes lines: `+` = SHA differs from index,
    `-` = uninitialized, `U` = merge conflict. Any of these means transparent
    stash cannot isolate the submodule's working tree (`git stash` only
    touches the parent's pointer entry, not the submodule's index).
    """
    try:
        cp = _run(["git", "submodule", "status"], cwd=base)
    except RuntimeError:
        # No `.gitmodules` or git config quirk → treat as no submodules.
        return
    bad: list[str] = []
    for line in cp.stdout.splitlines():
        if line and line[0] in "+-U":
            parts = line.split()
            bad.append(parts[1] if len(parts) >= 2 else line)
    if bad:
        raise RuntimeError(
            "[finalize] submodule state cannot be transparently isolated — "
            "please commit or reset submodule changes before finalize.\n"
            f"Submodules with state: {bad}"
        )


_HARNESS_ARTIFACT_PREFIXES = (
    ".worktrees/",
    ".claude/.hm-loop-",
    ".claude/.hm-finalize-stash-",
    # Pre-create reservation (PLAN-worktree-prune-create-race). A reservation
    # leaked by a hard kill (no `finally`) must be recognized as harness churn so a
    # peer's finalize never stashes it and it never surfaces as committable dirt —
    # parity with the other two transient `.hm-*` markers (REVIEW consensus P2).
    ".claude/.hm-creating-",
    # PLAN-spec-requirement-gate ADR-009: durable one-shot resume markers are
    # slug-suffixed (`.hm-spec-need-{slug}`) so they MUST be a PREFIX match, not
    # an exact-match churn-file entry. Registered here so a present marker does
    # NOT trip the dirty-base guard or get stashed at finalize.
    ".claude/.hm-spec-need-",
)


def _porcelain_path(porcelain_line: str) -> str | None:
    """Extract the path from a ``git status --porcelain`` v1 line, or None.

    Format: ``XY <path>`` — a 2-char status code, a space, then the path at
    column 3. Handles rename entries (``old -> new`` → the destination) and
    git's quote-wrapping for paths with special chars. Returns None when the
    line is too short to carry a path. Single source for the three sites that
    previously inlined (divergent) copies of this parse — P3 of
    PLAN-p6-p7-worktree-finalize.
    """
    if len(porcelain_line) < 4:
        return None
    path = porcelain_line[3:].strip()
    # Rename: `old -> new` → take the destination.
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()
    # Strip git's quote-wrapping (added for paths with spaces/special chars).
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    return path


def _is_harness_artifact(porcelain_line: str) -> bool:
    """Return True if a porcelain status line refers to a path we manage.

    Harness-managed paths are excluded from the "is base dirty" check so users
    who don't gitignore ``.worktrees/`` etc. don't see spurious stash activity
    (the artifacts get carried by the stash anyway when real user dirty is
    present; we just don't TRIGGER on them).
    """
    path = _porcelain_path(porcelain_line)
    if path is None:
        return False
    # ADR-002: `.gitignore` is co-managed — `_ensure_harness_gitignore` appends
    # churn patterns to it at create/make, which shows as `M .gitignore`. That
    # must NOT trip the dirty-base guard or get stashed at finalize (doing so
    # would recreate the very churn this work removes). Safe because the
    # finalize squash only carries the worktree branch's diff and never touches
    # the base `.gitignore`, so a user's own `.gitignore` edit is left intact.
    if path == ".gitignore":
        return True
    # ADR-003: recognize the shared churn set IN ADDITION to the legacy 3
    # prefixes (union). Dir churn matches by prefix; file churn matches
    # EXACTLY so sibling names (`...p5-batch-state.yaml.bak`) are not forgiven.
    # This stays a strict subset of `.claude/` + the two work-docs/ churn
    # paths — it does NOT forgive `.claude/agents`, `.claude/skills`,
    # `.claude/harness.yaml`, etc., so genuine user `.claude/` edits are still
    # preserved by the finalize stash (narrow-filter invariant).
    return (
        path.startswith(_HARNESS_ARTIFACT_PREFIXES)
        or path.startswith(_HARNESS_CHURN_DIRS)
        or path in _HARNESS_CHURN_FILES
    )


def _match_stash_sha(listing_stdout: str, message: str) -> str | None:
    """Find the stash SHA carrying our unique `message` in
    ``git stash list --pretty=format:%H %gs`` output, or None.

    Matches `message` as a SUBSTRING of the subject. git renders the subject as
    ``On <branch>: <message>`` and some versions append extra (e.g. a file
    count), so an exact / endswith match could miss a stash that genuinely
    exists and raise — orphaning the just-pushed stash (CR2 of
    PLAN-p6-p7-worktree-finalize REVIEW). Collision-safety rests on the
    freshly-generated 32-hex `uuid4().hex` SUFFIX of `message` (128 bits) — NOT
    the wt_name's 12-hex id — so another session's subject cannot coincide.
    Returns None only when no entry carries the message (genuinely absent →
    caller raises; nothing orphaned).
    """
    for line in listing_stdout.splitlines():
        if not line:
            continue
        sha, _, subject = line.partition(" ")
        if len(sha) != 40 or not _SHA_RE.match(sha):
            continue
        if message in subject:
            return sha
    return None


def _stash_base_dirty(base: Path, wt_name: str) -> str | None:
    """Stash base's dirty (tracked + staged + untracked) before squash.

    Returns the stash's 40-char commit SHA when something was stashed, or
    None when base was clean / only harness-managed artifacts are present.

    Race-free SHA capture: ADR-001 originally specified ``git stash create`` +
    ``git stash store`` to avoid the ``rev-parse stash@{0}`` window, but
    ``git stash create`` does NOT include untracked files (no ``-u`` flag on
    that subcommand — verified against git source). We instead use
    ``git stash push -u`` with a UUID-suffixed message to guarantee global
    uniqueness, then resolve the SHA via ``git stash list --pretty=format:'%H %gs'``
    matched on the exact full message. Because the message is unique, position
    drift in the stash stack from concurrent pushers cannot misidentify our
    entry — we always find OUR commit by message content (a property of the
    commit, not its reflog position).
    """
    status = _run(["git", "status", "--porcelain"], cwd=base)
    user_lines = [line for line in status.stdout.splitlines() if not _is_harness_artifact(line)]
    if not user_lines:
        return None
    # UUID suffix gives globally-unique stash messages — eliminates the
    # numeric-suffix substring collision class entirely and rules out any
    # cross-process message clash (git GUI, sibling session, Cursor IDE).
    # Full 32-char UUID — 128 bits of entropy makes coincident message clash
    # cryptographically infeasible. Stash messages aren't user-displayed in
    # casual use; length doesn't matter (REVIEW M-P1-3 closure).
    unique = uuid.uuid4().hex
    message = f"{_STASH_MESSAGE_PREFIX}{wt_name}-{unique}"
    _run(
        ["git", "stash", "push", "-u", "-m", message],
        cwd=base,
        timeout=_GIT_TIMEOUT_LONG,
    )
    # `--pretty=format:'%H %gs'` prints `<sha> <subject>` per stash entry;
    # subject is the message body without the `On <branch>:` prefix.
    listing = _run(["git", "stash", "list", "--pretty=format:%H %gs"], cwd=base)
    sha = _match_stash_sha(listing.stdout, message)
    if sha is not None:
        return sha
    raise RuntimeError(f"stash push reported success but no entry matches message {message!r}")


def _classify_pop_failure(error_text: str, base: Path) -> tuple[str, list[Path]]:
    """Return (class, files). class ∈ {merge_conflict, untracked_collision, unknown}.

    untracked_collision: git stash pop refuses to overwrite untracked files
      already created in the working tree (e.g., by the just-completed squash).
      Stderr contains "could not restore untracked files".
    merge_conflict: stash pop applied but left `<<<<<<<` markers in tracked
      files. Detected by `git diff --diff-filter=U`.
    """
    if "could not restore untracked files" in error_text:
        # Best-effort filename extraction from stderr; falls back to empty list
        # when git's output format changes. Step 5 LLM still gets actionable
        # guidance from the signal + stash ref.
        files: list[Path] = []
        for raw in error_text.splitlines():
            stripped = raw.strip()
            # Skip git's diagnostic preamble; collect bare-looking filenames.
            if (
                stripped
                and not stripped.endswith(":")
                and "could not" not in stripped
                and "stderr:" not in stripped
                and " " not in stripped
            ):
                files.append(Path(stripped))
        return ("untracked_collision", files)
    try:
        cp = _run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=base)
        conflicted = [Path(p) for p in cp.stdout.split() if p.strip()]
    except RuntimeError:
        conflicted = []
    if conflicted:
        return ("merge_conflict", conflicted)
    return ("unknown", [])


def _restore_base_dirty(base: Path, ref_sha: str) -> tuple[bool, str, list[Path]]:
    """Apply the stash by SHA then drop the matching reflog entry.

    `git stash pop <sha>` does NOT accept arbitrary SHAs — git requires the
    ``stash@{N}`` reflog form. ``git stash apply <sha>`` DOES accept any commit
    that "looks like a stash entry", which our captured SHA is. So we use
    `apply` (race-free SHA target) then locate the matching `stash@{N}` and
    drop it manually. Position drift is irrelevant: even if the reflog
    position shifted, we identify our entry by SHA equality (`--format=%H`)
    not by index.

    Success → (True, "", []). On apply failure stash is preserved with
    classified signal; on drop failure (apply succeeded but cleanup missed)
    we still return success — the user has their work back, and a leftover
    stash entry is a low-impact disk leak resolvable by hand.
    """
    try:
        _run(["git", "stash", "apply", ref_sha], cwd=base)
    except RuntimeError as e:
        klass, files = _classify_pop_failure(str(e), base)
        return (False, klass, files)
    # Apply succeeded — find the matching reflog ENTRY by refname and drop it.
    # Use `--format='%gd %H'` so we read the `stash@{N}` refname AND the SHA in
    # one git call. Dropping by refname (e.g. `stash@{0}`) eliminates the
    # enumerate-then-stale-index race the prior implementation had: even if a
    # concurrent push shifted the stack between our enumeration and our drop,
    # the refname `%gd` captures git's own naming at the moment of the list
    # call. (Residual one-step race: a push landing BETWEEN list and drop is
    # the same single-window race git itself has — unavoidable.)
    dropped = False
    try:
        listing = _run(["git", "stash", "list", "--format=%gd %H"], cwd=base)
        for line in listing.stdout.splitlines():
            stash_refname, _, sha = line.partition(" ")
            if sha.strip() == ref_sha and stash_refname.startswith("stash@{"):
                _run(["git", "stash", "drop", stash_refname], cwd=base)
                dropped = True
                break
    except RuntimeError:
        # Best-effort: apply already restored the user's work. Leaking a stash
        # entry is far better than losing the apply.
        pass
    if not dropped:
        # SHA didn't match any stash entry — likely already dropped by the user
        # or removed via reflog gc. Surface a warning so the leak is visible
        # (REVIEW round 2 P2: silent stash leak when SHA not found).
        print(
            f"[finalize] stash drop skipped — SHA {ref_sha[:8]} not found in "
            f"reflog (stash may be leaked; check `git stash list`)",
            file=sys.stderr,
        )
    return (True, "", [])


def _fenced_restore_base_dirty(base: Path, ref_sha: str) -> tuple[bool, str, list[Path]]:
    """`_restore_base_dirty` serialized behind the merge fence (CN2 of
    PLAN-p6-p7-worktree-finalize REVIEW, supersedes ADR-003's "pops stay outside
    the fence").

    Two parallel finalizes against the same base otherwise race on the shared
    stash stack / base ``index.lock`` during ``git stash apply``+``drop``. The
    fence serializes them. If the fence is unavailable (TimeoutError or an
    unsupported-lock RuntimeError), fall back to an UNFENCED restore — popping
    the user's work back matters more than serializing it, and the apply/drop is
    already SHA-targeted (wrong-entry-safe), so the unfenced path is exactly the
    pre-change behavior.
    """
    try:
        with _acquire_merge_fence(base, timeout=_FENCE_TIMEOUT):
            return _restore_base_dirty(base, ref_sha)
    except (RuntimeError, TimeoutError):
        return _restore_base_dirty(base, ref_sha)


def _emit_pop_failure_signal(klass: str, ref_sha: str, files: list[Path], wt_name: str) -> None:
    """Write the literal stderr block Step 5 LLM matches on (ADR-003).

    Recovery hints use ``ref_sha[:8]`` for discoverability via
    `git stash list | grep <prefix>` — full SHA in `Stash:` line for precision.
    """
    short = ref_sha[:8]
    drop_hint = (
        f"git stash drop $(git stash list --format='%gd %H' | grep {short} | awk '{{print $1}}')"
    )
    if klass == "merge_conflict":
        signal = _POP_CONFLICT_SIGNAL
        recovery = f"Resolve: grep -l '<<<<<<<' . then edit + git add + {drop_hint}"
    elif klass == "untracked_collision":
        signal = _UNTRACKED_COLLISION_SIGNAL
        recovery = (
            f"Recover: git checkout {ref_sha} -- <file> (rename first if needed) then {drop_hint}"
        )
    else:
        signal = _POP_UNKNOWN_SIGNAL
        recovery = f"Inspect: git stash show -p {ref_sha}; resolve manually; {drop_hint}"
    print(signal, file=sys.stderr)
    print(f"Stash: {ref_sha} ({_STASH_MESSAGE_PREFIX}{wt_name})", file=sys.stderr)
    label = "Files (in stash, not restored)" if klass == "untracked_collision" else "Files"
    print(f"{label}: {[str(f) for f in files]}", file=sys.stderr)
    print(f"Find: git stash list | grep {short}", file=sys.stderr)
    print(recovery, file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────────────
# Stage-only handshake: finalize writes a stash-ref file; wrapup's
# `post-commit-pop` CLI pops it AFTER its commit (ADR-001 §2).
# ──────────────────────────────────────────────────────────────────────────────

_STASH_REF_PREFIX = ".hm-finalize-stash-"
_STASH_REF_GITIGNORE_PATTERN = ".claude/.hm-finalize-stash-*"


def _stash_ref_path(base: Path, wt_name: str) -> Path:
    """Return the per-worktree stash-ref file path under ``<base>/.claude/``."""
    return base / _LOOP_MARKER_DIR / f"{_STASH_REF_PREFIX}{wt_name}"


def _count_pending_stashes(claude_dir: Path) -> int:
    """Count live `.hm-finalize-stash-*` ref files in `<base>/.claude/`.

    PLAN-worktree-cross-session-data-loss-defense ADR-003 queue-guard:
    `worktree create` ABORTs when ≥2 live refs exist, because that's the
    canonical "wrapup not run between exec-rev turns" footgun signature.
    Stale refs with absent session markers are cleanup artifacts, not active
    multi-session pressure, and must not block unrelated worktree creation.
    Missing dir → 0 (clean state).

    PLAN-fleet-10-20-parallel-safety C3 (REVERTED — DO NOT re-attempt naively):
    excluding FOREIGN-owned live stashes from this count to relieve the fleet
    false-block re-opens the 3×-recurring `worktree-finalize-pulls-orphan-wip-
    into-main` contamination. The reason this guard counts foreign stashes is
    LOAD-BEARING: Layer 3 (`post-commit-pop`'s `HM_OWNED_SESSION_UUIDS` set,
    sourced from `_owned_session_uuids`) is itself documented-vulnerable — it
    reads ALL sessions' `.hm-loop-*` markers, so a session's `post-commit-pop`
    will restore a PEER's deferred stash (see the comment at `_cli_post_commit_pop`
    "preserves prior (vulnerable) behavior"). Blocking create while foreign
    stashes exist is the operative gate that keeps the peer out of that path.
    Safe per-session exclusion requires hardening Layer 3 first (the per-session
    `--owned-uuid` wiring the post-commit-pop comment describes as a follow-up).
    """
    if not claude_dir.is_dir():
        return 0
    count = 0
    for ref_file in claude_dir.glob(f"{_STASH_REF_PREFIX}*"):
        fields = _validate_stash_ref_fields(_read_stash_ref_file(ref_file))
        if fields is None:
            continue
        if _session_marker_present(fields["session_marker"]):
            count += 1
    return count


# PLAN-worktree-cross-session-data-loss-defense ADR-002 dirty-base guard
# uses a SEPARATE harness-artifact filter that also excludes the whole
# `.claude/` directory (any path starting with `.claude/`). Why separate
# from `_is_harness_artifact`: that helper is also used by the finalize
# stash logic, which DOES need to preserve `.claude/` user edits (custom
# agents/skills/commands committed there). At create-time the user has no
# legitimate need to keep `.claude/` dirt — real-world users gitignore
# the whole dir anyway. Splitting the predicates makes the test-fixture
# coverage clean without weakening finalize-stash preservation.
def _is_create_guard_harness_artifact(porcelain_line: str) -> bool:
    """True iff line is harness-managed for the dirty-base guard's purposes."""
    # ADR-003: the delegated `_is_harness_artifact` now recognizes the shared
    # churn set, including the work-docs/ churn paths (loop-context,
    # p5-batch-state) — so committed+modified churn OUTSIDE `.claude/` no
    # longer blocks `create`. No separate work-docs branch needed here.
    if _is_harness_artifact(porcelain_line):
        return True
    path = _porcelain_path(porcelain_line)
    if path is None:
        return False
    # PLAN-worktree-deliverable-blocks-create ADR-001: forgive deliverable docs
    # at CREATE time only (finalize's `_is_harness_artifact` still preserves
    # them). Per-line: coexisting code WIP keeps tripping the guard.
    if _is_deliverable_path(path):
        return True
    return path.startswith(".claude/") or path == ".claude"


def _has_user_dirty_state(base: Path) -> bool:
    """True iff `git status --porcelain` shows USER-owned dirt (not harness).

    PLAN-worktree-cross-session-data-loss-defense ADR-002 dirty-base guard:
    `worktree create` ABORTs when base has uncommitted USER changes — the
    canonical 'finalize-pulls-orphan-wip-into-main' setup ([fail:design]
    count:2 → 3rd 2026-05-23). Filter via `_is_create_guard_harness_artifact`
    which excludes `.claude/` entirely (real users gitignore it).

    `-uall` (PLAN-worktree-deliverable-blocks-create ADR-001): expand untracked
    directories to individual files so the per-line deliverable/harness filter
    sees `work-docs/PLAN-x.md` rather than a collapsed `work-docs/` line (git
    collapses a fully-untracked dir by default). Without it, a fresh project's
    first PLAN would still block create.
    """
    try:
        status = _run(["git", "status", "--porcelain", "-uall"], cwd=base)
    except RuntimeError:
        return False  # Not a git repo or git unavailable — let downstream fail naturally.
    user_lines = [
        line for line in status.stdout.splitlines() if not _is_create_guard_harness_artifact(line)
    ]
    return bool(user_lines)


def _list_user_dirty_files(base: Path) -> list[str]:
    """Return the user-dirty filenames for the abort-message listing."""
    try:
        # `-uall` so the listing matches `_has_user_dirty_state`'s per-line view
        # (ADR-001) — collapsed untracked dirs would otherwise hide the real file.
        status = _run(["git", "status", "--porcelain", "-uall"], cwd=base)
    except RuntimeError:
        return []
    out: list[str] = []
    for line in status.stdout.splitlines():
        if _is_create_guard_harness_artifact(line):
            continue
        path = _porcelain_path(line)
        if path is not None:
            out.append(path)
    return out


def _old_model_residue_blockers(base: Path, label: str) -> list[str]:
    """Filesystem-only old-model pending-state probes for ONE repo base (RAW
    marker-agnostic globs — a bare ref/dir with no live marker still blocks; the
    marker-gated `_count_pending_stashes` would false-pass it). `label` annotates
    sibling bases in the warning."""
    claude = base / _LOOP_MARKER_DIR
    out: list[str] = []
    if claude.is_dir() and any(claude.glob(f"{_STASH_REF_PREFIX}*")):
        out.append(f"unpopped finalize stash (.hm-finalize-stash-*){label}")
    if claude.is_dir() and any(claude.glob(f"{_LOOP_MARKER_PREFIX}*")):
        out.append(f"active loop marker (.hm-loop-*){label}")
    worktrees = base / WORKTREE_DIR_NAME
    if worktrees.is_dir() and any(
        p.is_dir() and p.name.startswith(_OWNED_PREFIXES) for p in worktrees.iterdir()
    ):
        # ALL owned old-model prefixes, not just `execute-` — `_OWNED_PREFIXES`
        # single-source-of-truth (REVIEW code P1): a crashed session under a
        # non-`execute` workflow name leaves residue with no live marker, which an
        # `execute-*`-only glob would miss → flip-while-stranded.
        out.append(f"in-flight old-model worktree (.worktrees/<owned-prefix>-*){label}")
    return out


def _git_dirt_blocker(base: Path, label: str) -> list[str]:
    """Read-only `git status` dirt/indeterminate probe for ONE base, with the same
    `label` annotation convention as `_old_model_residue_blockers` so it applies to
    PRIMARY (`label=""`) and sibling (`label=" [sibling X]"`) bases identically.

    A non-git base has no git state → `[]`. Uncommitted USER dirt blocks; a status
    FAILURE inside a git repo is INDETERMINATE → defer (REVIEW security/Codex P2:
    don't report a flaky clean). Never MUTATES git."""
    if not (base / ".git").exists():
        return []
    try:
        status = _run(["git", "status", "--porcelain", "-uall"], cwd=base)
    except RuntimeError:
        return [f"could not verify base cleanliness (git status failed){label}"]
    if any(not _is_create_guard_harness_artifact(ln) for ln in status.stdout.splitlines()):
        return [f"uncommitted user changes in the base repo{label}"]
    return []


def enablement_preflight(
    target: Path, *, sibling_bases: list[Path] | None = None
) -> tuple[bool, str | None]:
    """ADR-008 make-time migration probe: is the project clean enough to flip
    `worktree.feature_branch_workflow` → True?

    Returns `(should_flip, warning)`. Flips ONLY when there is NO pending old-model
    state — in the PRIMARY base AND every sibling base — so the new in-worktree path
    can never strand work that only the old `post-commit-pop` would finalize. The
    sibling sweep mirrors `_cli_post_commit_pop`'s per-sibling drain: a multi-repo
    Production harness keeps per-sibling stash refs / worktrees while the loop marker
    lives only on the primary, so a sibling-only pending state with a clean primary
    must still block (REVIEW security P1).

    Blockers per base (PRIMARY and every sibling, full parity — Phase 7 AC4): any
    `.hm-finalize-stash-*` ref, any live `.hm-loop-*` marker, any in-flight
    `.worktrees/<owned-prefix>-*` dir, PLUS a read-only `git status` dirty/
    indeterminate probe (uncommitted user dirt blocks; a status FAILURE inside a git
    repo defers). A non-git base has no git state → no git block. **Trade-off:** N
    siblings → N defer-on-flake surfaces; safety-biased (defer > false-clean) and
    accepted — the one-shot flip stays on old-model + warns, recoverable by re-run.
    Filesystem-only apart from the read-only status calls — never MUTATES git."""
    bases: list[tuple[Path, str]] = [(target, "")]
    bases += [(sib, f" [sibling {sib.name}]") for sib in sibling_bases or []]
    blockers: list[str] = []
    for base, label in bases:
        blockers += _old_model_residue_blockers(base, label)
        blockers += _git_dirt_blocker(base, label)
    if blockers:
        return False, (
            "feature-branch workflow deferred: drain in-flight work then re-run "
            f"make — pending: {', '.join(blockers)}"
        )
    return True, None


def disable_preflight(
    target: Path, *, sibling_bases: list[Path] | None = None
) -> tuple[bool, str | None]:
    """Symmetric counterpart of :func:`enablement_preflight` — may isolation be
    turned OFF right now? (PLAN-worktree-side-defaults ADR-003.)

    Returns ``(may_disable, refusal)``. The upgrade direction had a clean-live-state
    probe from the start; the downgrade direction had none, so a `--preset Side`
    flip moved a project with live `hm/<slug>` worktrees back onto the legacy model
    with zero output. That is the precondition class of the count:3
    `worktree-finalize-pulls-orphan-wip-into-main` contamination — and once the OFF
    render also stops emitting the finalize/stash recovery instructions, the
    stranded state has no documented way back.

    Blockers are the same residue set the enablement probe uses, minus the
    user-dirt probe: ordinary uncommitted work is not a reason to refuse a config
    change, whereas a live task worktree / pending finalize stash / live loop marker
    is. Filesystem + read-only git only; never MUTATES anything.
    """
    bases: list[tuple[Path, str]] = [(target, "")]
    bases += [(sib, f" [sibling {sib.name}]") for sib in sibling_bases or []]
    blockers: list[str] = []
    live_foreign = False
    for base, label in bases:
        blockers += _old_model_residue_blockers(base, label)
        wt_blockers, saw_live = _task_worktree_blockers(base, label)
        blockers += wt_blockers
        live_foreign = live_foreign or saw_live
        blockers += _unlanded_task_branch_blockers(base, label)
    if blockers:
        # The remedy is liveness-aware on purpose: `task-land` on a worktree another
        # session is actively writing in squashes its half-finished branch into base and
        # deletes the directory underneath it — the contamination class this guard was
        # added to prevent, triggered by the guard's own advice.
        remedy = (
            "One or more of these belong to a LIVE session (see the (LIVE …) tags). "
            "Stop that session or wait for it — do NOT `task-land` a worktree another "
            "session is writing in."
            if live_foreign
            else "Land or discard it first (`/hm:wrapup`, or `hm worktree task-land <slug>`)."
        )
        return False, (
            "refusing to disable worktree isolation — in-flight work would be "
            f"stranded: {', '.join(blockers)}\n"
            f"{remedy} Then re-run."
        )
    return True, None


def _task_worktree_blockers(base: Path, label: str) -> tuple[list[str], bool]:
    """Per-task worktrees (`hm/<slug>`) in ``base``, plus whether any looked LIVE.

    Fail-CLOSED, unlike `_is_task_worktree`'s own fail-open contract: that predicate
    exists for the finalize dispatch, where "not a task worktree" routes to the legacy
    path. Here the same False would mean "nothing to strand, go ahead and disable", so a
    directory whose branch cannot be read — a detached HEAD mid-`task-refresh` rebase,
    a git error, a permission problem — is reported as an INDETERMINATE blocker rather
    than waved through. Mirrors `_git_dirt_blocker`'s defer-on-failure stance.
    """
    wt_root = base / WORKTREE_DIR_NAME
    try:
        if not wt_root.is_dir():
            return [], False
        entries = sorted(wt_root.iterdir())
    except OSError as exc:
        return [
            f"cannot enumerate {wt_root}{label} ({type(exc).__name__}) — assuming in flight"
        ], False

    live_rows = {row.worktree: row for row in _read_sessions(base) if _pid_alive(row.pid)}
    out: list[str] = []
    saw_live = False
    for d in entries:
        try:
            if not d.is_dir() or not (d / ".git").exists():
                continue
            branch = _current_branch(d)
        except (OSError, RuntimeError) as exc:
            out.append(
                f"task worktree {d.name}{label} — branch unresolvable ({type(exc).__name__})"
            )
            continue
        if branch == "HEAD":
            out.append(f"task worktree {d.name}{label} — detached HEAD (mid-rebase?)")
            continue
        if not branch.startswith(_TASK_BRANCH_PREFIX):
            continue
        row = live_rows.get(str(d)) or live_rows.get(str(d.resolve()))
        if row is not None:
            saw_live = True
            out.append(f"task worktree {d.name}{label} (LIVE — pid {row.pid})")
        else:
            out.append(f"task worktree {d.name}{label}")
    return out, saw_live


def _unlanded_task_branch_blockers(base: Path, label: str) -> list[str]:
    """`hm/*` branches with no landed marker, even when the worktree dir is gone.

    In the per-task model the durable unit of work is the BRANCH — `cleanup` removes the
    directory but never the branch, so a crash or a manual `git worktree remove` leaves
    branch-only state that a directory-only probe cannot see.
    """
    try:
        cp = _run(
            [
                "git",
                "for-each-ref",
                "--format=%(refname:short)",
                f"refs/heads/{_TASK_BRANCH_PREFIX}*",
            ],
            cwd=base,
        )
    except RuntimeError:
        return []
    out: list[str] = []
    for branch in cp.stdout.split():
        if not _landed_marker_matches_tip(base, branch):
            out.append(f"unlanded branch {branch}{label}")
    return out


def _landed_marker_matches_tip(base: Path, branch: str) -> bool:
    """True when `refs/hm-landed/v1/<branch>` records this branch's current tip."""
    try:
        marker = _run(
            ["git", "rev-parse", f"{_LANDED_REF_PREFIX}{branch}"], cwd=base
        ).stdout.strip()
        tip = _run(["git", "rev-parse", branch], cwd=base).stdout.strip()
    except RuntimeError:
        return False
    return bool(marker) and marker == tip


def _list_pending_stash_refs(claude_dir: Path) -> list[str]:
    """Return live ref-file basenames for the abort-message listing."""
    if not claude_dir.is_dir():
        return []
    out: list[str] = []
    for ref_file in claude_dir.glob(f"{_STASH_REF_PREFIX}*"):
        fields = _validate_stash_ref_fields(_read_stash_ref_file(ref_file))
        if fields is not None and _session_marker_present(fields["session_marker"]):
            out.append(ref_file.name)
    return sorted(out)


# PLAN-worktree-cross-session-data-loss-defense ADR-004 Session UUID
# ──────────────────────────────────────────────────────────────────────────────
# Replace the file-exists `_session_marker_present` check with UUID-based
# ownership. UUID embeds in worktree dirname (`execute-{uuid}-{ts}`) for
# durable create→finalize binding without a side-channel state file.
# ──────────────────────────────────────────────────────────────────────────────

_SESSION_UUID_FILENAME = ".hm-session-uuid"
_SESSION_UUID_GITIGNORE_PATTERN = ".claude/.hm-session-uuid"
_SESSION_UUID_LEGACY_SENTINEL = "legacy"


def _current_session_uuid(project_root: Path) -> str:
    """Return the 12-hex session UUID for ``project_root``.

    Persists to ``<project_root>/.claude/<filename>`` on first call so all
    subsequent invocations in the same project read back the same UUID.
    `.claude/` is created if missing. Different projects → independent UUIDs.

    Atomic write + gitignore registration (REVIEW round 1 P0-CON1) — prevents
    commit-to-public leak that would defeat cross-collaborator isolation.
    TOCTOU race (REVIEW round 1 P1-MAN3) mitigated by re-reading the file
    after atomic_write — last-writer wins; loser silently picks up winner's
    value, so concurrent first-callers can't end up with different UUIDs.

    **REVIEW round 1 P0-MANUAL2 acknowledged**: this is project-scoped, not
    session-scoped. Persistent shared UUID means cross-session isolation
    DOES NOT actually fire on the same project. Real fix is dirname-embedded
    UUID per ADR-004 §2 — deferred as substantive refactor (task #10
    expanded). This helper keeps the API stable for the in-flight wiring;
    the dirname-embed migration replaces the persistent-file approach.
    """
    claude_dir = project_root / _LOOP_MARKER_DIR
    claude_dir.mkdir(parents=True, exist_ok=True)
    uuid_path = claude_dir / _SESSION_UUID_FILENAME
    if uuid_path.is_file():
        existing = uuid_path.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{12}", existing):
            return existing
    new_uuid = uuid.uuid4().hex[:12]
    atomic_write(uuid_path, new_uuid)
    # P0-CON1 fix: ensure UUID file never commits to public repo (peer
    # _write_loop_marker + _write_stash_ref_file both call this).
    _ensure_gitignore_entry(project_root, _SESSION_UUID_GITIGNORE_PATTERN)
    # P1-MAN3 fix: re-read AFTER atomic_write so concurrent first-callers
    # don't both return their own losing UUID. Last-writer wins on disk;
    # both readers converge on the same value.
    persisted = uuid_path.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[0-9a-f]{12}", persisted):
        return persisted
    return new_uuid


def _session_owns_marker(ref_session_uuid: str, current_session_uuid: str) -> bool:
    """True iff the ref's session_uuid matches the current process's UUID.

    Empty `ref_session_uuid` (pre-Phase-3 ref file with no `session_uuid`
    field) → False; one-shot legacy-sentinel migration handles those at the
    post-commit-pop layer, not here. `current_session_uuid` is the value
    returned by `_current_session_uuid` for the current project root.
    """
    if not ref_session_uuid or not current_session_uuid:
        return False
    return ref_session_uuid == current_session_uuid


# PLAN-worktree-cross-session-data-loss-defense ADR-005 merge fence
# ──────────────────────────────────────────────────────────────────────────────
# Primary: fcntl.flock (advisory POSIX lock). Secondary (equal-status, NOT
# silent skip): os.open(O_CREAT|O_EXCL|O_WRONLY) polling loop. WSL2/NTFS is
# the primary project runtime — silent skip on WSL2 would degrade Layer 4
# to ZERO protection, incompatible with the "절대 X" invariant.
# ──────────────────────────────────────────────────────────────────────────────


def _flock_lock(lock_path: Path, timeout: float) -> tuple[int | None, str]:
    """Try fcntl.flock; return (fd, "flock") on success or (None, "unsupported")."""
    import errno
    import fcntl

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY, 0o600)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd, "flock"
        except OSError as exc:
            if exc.errno in (errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP):
                os.close(fd)
                return None, "unsupported"
            if time.monotonic() >= deadline:
                os.close(fd)
                raise TimeoutError(
                    f"merge fence flock timeout after {timeout}s on {lock_path}"
                ) from exc
            time.sleep(0.05)


def _parse_excl_body(body: str) -> tuple[str | None, int | None, float | None]:
    """Parse the 3-line O_EXCL lock body ``nonce\\npid\\ntimestamp`` (ADR-003).

    Returns ``(nonce, pid, ts)``; any individual unparseable field → ``None``.
    A fully empty/legacy body → ``(None, None, None)`` (routes reaping to the
    age-gated path rather than the pid-liveness path).
    """
    lines = body.splitlines()
    if len(lines) < 3:
        return (None, None, None)
    nonce = lines[0].strip() or None
    try:
        pid: int | None = int(lines[1].strip())
    except ValueError:
        pid = None
    try:
        ts: float | None = float(lines[2].strip())
    except ValueError:
        ts = None
    return (nonce, pid, ts)


def _reap_if_stale(lock_path: Path) -> bool:
    """Reap a stale O_EXCL lock IFF its holder is provably gone (ADR-003).

    Liveness-gated — a LIVE holder is never reaped by age (Codex P0: the fence
    acquire-timeout bounds waiting, not hold time, so a slow/hung-but-live land
    legitimately holds the lock). Rules: pid parseable + dead → reap; pid
    parseable + alive → keep (the safe over-preservation direction, including a
    reused pid); body unparseable/legacy → reap only when mtime exceeds
    ``_EXCL_STALE_AGE``. The unlink is nonce/identity re-checked against the body
    observed at decision time, so a successor that recreated the lock between the
    decision and the unlink (Codex P1) is never removed. Returns True iff reaped.
    """
    try:
        body = lock_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True  # already gone — caller can retry the create immediately
    except OSError:
        return False
    _nonce, pid, _ts = _parse_excl_body(body)
    if pid is not None:
        if _pid_alive(pid):
            return False  # live holder — never reaped by age
        # holder genuinely dead → fall through to the identity-checked unlink
    else:
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            return False
        if age <= _EXCL_STALE_AGE:
            return False  # fresh empty body (e.g. SIGKILL in create→write window)
    return _reap_stale_file(lock_path, body)


def _reap_stale_file(lock_path: Path, expected_body: str) -> bool:
    """Atomically claim a stale O_EXCL lock via rename, then verify + remove.

    REVIEW k-of-3 P1 (concurrency + Codex): the prior compare-then-``unlink()``
    removed the lock BY PATHNAME, so if a peer reaper removed the dead holder and a
    live successor recreated the lock between the equality check and the unlink,
    this process unlinked the *successor's live* lock — re-opening the very O_EXCL
    mutual-exclusion failure the hardening closes. Fix: ``os.replace`` moves the
    stale file to a private, uniquely-named quarantine in ONE atomic step, so
    (a) exactly one reaper wins — losers get ``FileNotFoundError``; (b) we only
    ever ``unlink`` our private quarantine name, never the live lock at the
    original path, which is immediately free for a successor's fresh create.

    Residual (accepted, self-healing): if a successor recreated the lock in the
    decision→rename window, ``os.replace`` grabs the successor's body instead; the
    body-verify catches the mismatch and restores it via ``os.link`` (which
    fail-safes on ``FileExistsError`` — never clobbering a yet-newer holder). A
    live successor is never age-reaped, so any third-order disruption self-heals on
    the next acquire. Returns True iff a genuinely-stale lock was removed.
    """
    quarantine = lock_path.with_name(f".{lock_path.name}.reap-{uuid.uuid4().hex}")
    try:
        os.replace(lock_path, quarantine)
    except FileNotFoundError:
        return True  # a peer reaped it first — original path is free to recreate
    except OSError:
        return False
    try:
        grabbed = quarantine.read_text(encoding="utf-8")
    except OSError:
        grabbed = ""
    if grabbed == expected_body:
        # Cleanup of OUR OWN private quarantine must never propagate (REVIEW
        # re-review P3): a non-FNF OSError here would escape the merge fence.
        with contextlib.suppress(OSError):
            quarantine.unlink()
        return True
    # Grabbed a successor's fresh lock (recreated in the decision→rename window).
    # Restore via os.link — FileExistsError means a yet-newer holder already owns
    # the path, so we never clobber it; either way drop our quarantine name.
    with contextlib.suppress(OSError):
        os.link(str(quarantine), str(lock_path))
    with contextlib.suppress(OSError):
        quarantine.unlink()
    return False


def _excl_lock(lock_path: Path, timeout: float) -> tuple[int, str]:
    """O_EXCL polling lock — reliable on WSL2/NTFS when flock isn't (ADR-003).

    Returns ``(fd, nonce)``; caller must close ``fd`` AND release via
    ``_excl_release(lock_path, nonce)`` (identity-checked). On contention a
    genuinely-stale lock (dead holder, or an aged legacy body) self-heals via
    ``_reap_if_stale``; a live holder polls every 50ms until acquired or timeout.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    nonce = uuid.uuid4().hex
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if _reap_if_stale(lock_path):
                continue  # reaped a dead holder's lock — retry the create now
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"merge fence O_EXCL timeout after {timeout}s on {lock_path}"
                ) from None
            time.sleep(0.05)
            continue
        # Won the create — stamp the ownership body. A body-write FAILURE or short
        # write (ENOSPC/IO) would hand back a lock `_excl_release` can't identify by
        # nonce → an un-releasable file that wedges the fence until the 720s age
        # path (REVIEW Codex P2). Treat a failed/partial write as acquisition
        # failure: drop the half-written lock and keep polling. (A SIGKILL between
        # the create and this write still leaves an empty body — that narrow case
        # is the age-gated path, documented in ADR-003.)
        payload = f"{nonce}\n{os.getpid()}\n{time.time()}\n".encode()
        try:
            written = os.write(fd, payload)
        except OSError:
            written = -1
        if written != len(payload):
            os.close(fd)
            # We exclusively own this freshly-created lock (only-fd holder; a fresh
            # empty/partial body is not age-reapable for 720s, so no peer touches
            # it) — a direct unlink of our own lock is safe.
            with contextlib.suppress(FileNotFoundError):
                lock_path.unlink()
            if time.monotonic() >= deadline:
                raise TimeoutError(f"merge fence O_EXCL body-write failed on {lock_path}") from None
            time.sleep(0.05)
            continue
        return fd, nonce


def _excl_release(lock_path: Path, nonce: str) -> None:
    """Release an O_EXCL lock — unlink ONLY if it still carries OUR ``nonce``.

    Never removes a successor's lock (a reaped-then-recreated lock has a
    different nonce), closing the B-unlinks-C's-lock race (Codex P1).
    """
    try:
        current = lock_path.read_text(encoding="utf-8")
    except OSError:
        return
    cur_nonce, _pid, _ts = _parse_excl_body(current)
    if cur_nonce == nonce:
        with contextlib.suppress(FileNotFoundError):
            lock_path.unlink()


def _verify_scope_subset(
    base: Path,
    wt_branch: str,
    staged_before: set[str],
) -> tuple[bool, set[str]]:
    """ADR-006 finalize scope-guard: assert merge-introduced staged paths
    are a SUBSET of the worktree's own diff.

    Returns (ok, contamination_paths). `ok=False` ⇒ contamination_paths is
    the set of files staged by the merge that did NOT originate in the
    worktree branch. Caller decides whether to halt (Phase 7 promotes to
    halt-mode) or warn-only (Phase 5 initial behavior).

    `staged_before` is the set of paths staged in `base` BEFORE `git merge
    --squash` ran — captures pre-existing staged content from
    `--allow-dirty-base` paths so it doesn't false-positive the guard.

    `wt_branch` is the branch the worktree lived on (e.g. `execute-A-ts`).
    `git diff main...<wt-branch>` gives the wt's own delta against the
    merge-base — that's the allowed scope.
    """
    staged_after_proc = _run(["git", "diff", "--cached", "--name-only"], cwd=base)
    staged_after = set(staged_after_proc.stdout.strip().splitlines())
    delta = staged_after - staged_before

    # REVIEW round 1 P1-MAN1 fix: resolve base branch dynamically. Hard-coded
    # `main` silently fails (`unknown revision`) on repos whose default branch
    # is `master`/`develop`/etc — `except RuntimeError` swallows it and the
    # scope-guard degrades to a no-op. Use `merge-base` against the worktree
    # branch's upstream when available, else fall back to symbolic HEAD.
    try:
        # The wt branch was created from the base's HEAD at create time;
        # `git merge-base wt_branch HEAD` gives the common ancestor regardless
        # of the default-branch name.
        merge_base = _run(["git", "merge-base", wt_branch, "HEAD"], cwd=base).stdout.strip()
        wt_diff_proc = _run(["git", "diff", f"{merge_base}...{wt_branch}", "--name-only"], cwd=base)
    except RuntimeError:
        # Fall back to the original hard-coded `main` if merge-base fails
        # (very unusual — but preserves prior behavior as graceful degrade).
        wt_diff_proc = _run(["git", "diff", f"main...{wt_branch}", "--name-only"], cwd=base)
    wt_diff_paths = set(wt_diff_proc.stdout.strip().splitlines())

    contamination = delta - wt_diff_paths
    return (not contamination, contamination)


def _snapshot_staged_paths(base: Path) -> set[str]:
    """Paths currently staged in ``base`` (``git diff --cached --name-only``).

    PLAN-p6-p7-worktree-finalize ADR-003: captured INSIDE the merge fence,
    strictly AFTER ``_stash_base_dirty``, so the scope-guard's
    ``--allow-dirty-base`` exemption reads the post-stash index. Returns the
    empty set on git failure (degrade to "nothing pre-staged").
    """
    try:
        proc = _run(["git", "diff", "--cached", "--name-only"], cwd=base)
    except RuntimeError:
        return set()
    return set(proc.stdout.strip().splitlines())


@contextlib.contextmanager
def _acquire_merge_fence(  # type: ignore[no-untyped-def]
    base: Path, timeout: float = 60.0, lock_basename: str = "index.lock-hm"
):
    """Serialize a critical section across parallel processes on one repo.

    PLAN-worktree-cross-session-data-loss-defense ADR-005. Primary path:
    fcntl.flock on `<git-common-dir>/<lock_basename>`. Secondary (equal-status,
    NOT silent skip) when flock is unavailable: O_EXCL polling lock on
    `<git-common-dir>/<lock_basename>-excl`. Either path works on WSL2/NTFS.

    `lock_basename` selects the lock file: the finalize merge uses the default
    `index.lock-hm`; the Phase 1 session registry uses a DISTINCT
    `index.lock-hm-registry` so a registry mutate can never contend with — or,
    once wired inside a fenced finalize, self-deadlock against — the merge lock
    (REVIEW Phase 1 P1: shared non-reentrant fence + 60-vs-360s timeout mismatch).

    Lock file is harness-owned — `.git/` is gitignored so it never trips the
    dirty-base guard.
    """
    # REVIEW round 1 P0-MANUAL1 fix: use `git rev-parse --git-common-dir`
    # to resolve the SHARED gitdir across all worktrees of the same repo.
    # The naive `(base / ".git").is_dir()` check returns False for git
    # worktrees (where `.git` is a FILE containing `gitdir: ...`), routing
    # the lockfile to per-worktree paths and silently defeating Layer 4
    # for the parallel-worktree scenario the fence exists to protect.
    try:
        common_dir_str = _run(["git", "rev-parse", "--git-common-dir"], cwd=base).stdout.strip()
        common_dir = Path(common_dir_str)
        if not common_dir.is_absolute():
            common_dir = (base / common_dir).resolve()
        lock_dir = common_dir if common_dir.is_dir() else base
    except (RuntimeError, OSError):
        # Test fixtures pass tmp_path that isn't a real git repo — fall
        # back to <base>/ for unit tests.
        lock_dir = base
    flock_path = lock_dir / lock_basename
    excl_path = lock_dir / f"{lock_basename}-excl"

    fd, mechanism = _flock_lock(flock_path, timeout)
    if mechanism == "unsupported":
        # Secondary mechanism: O_EXCL atomic create (ADR-003: pid+nonce body,
        # liveness-gated reap-at-acquire, identity-checked release).
        excl_fd, excl_nonce = _excl_lock(excl_path, timeout)
        try:
            yield
        finally:
            os.close(excl_fd)
            _excl_release(excl_path, excl_nonce)
        return

    # flock path: fd holds the lock; close releases automatically.
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)


def _write_stash_ref_file(
    base: Path,
    wt_name: str,
    ref_sha: str,
    session_marker_path: Path,
    sibling_bases: list[Path] | None = None,
    session_uuid: str | None = None,
) -> Path:
    """Persist the stash handoff state (ADR-001 + ADR-002).

    Body is up to 5 ``key: value`` lines parsed by a trivial reader.
    Schema:
    - ``ref_sha``: 40-char immutable stash commit SHA (no position drift)
    - ``base``: absolute path to THIS repo's base (sibling in multi-repo)
    - ``session_marker``: absolute path to the PRIMARY repo's
      ``.claude/.hm-loop-{primary_wt_name}`` file
    - ``sibling_bases``: pipe (``|``)-separated absolute paths to peer repos
      (only written on the PRIMARY's ref file; empty for sibling refs). Used
      by ``_cli_post_commit_pop`` for multi-repo scan discovery — replaces
      reading ``harness.yaml`` at pop time, which was vulnerable to a
      chicken-and-egg deadlock if the yaml was swept into the stash itself.
      Paths containing ``|``, ``\n``, ``\r``, or NUL are REJECTED at write
      time (RuntimeError) rather than silently produce an ambiguous body
      (REVIEW round 4 P1).
    - ``created_at``: ISO 8601 UTC (forensic only)
    """
    from harness_maker.io_utils import atomic_write

    path = _stash_ref_path(base, wt_name)
    # Pipe-separated absolute paths inside a single body line (the line-based
    # parser splits each `key: value` at the first `:` — multi-line values
    # break it). `|` is legal in POSIX paths but extraordinarily rare; we
    # FAIL-FAST at write time if any sibling path contains `|`, `\n`, `\r`,
    # or NUL — same forbidden-character set the validator enforces at read
    # time. Without this guard the write would produce an ambiguous body
    # the validator would silently reject at pop time, leaving stash leaked
    # with no diagnostic (REVIEW round 4 P1).
    sibling_strs: list[str] = []
    for p in sibling_bases or []:
        s = str(p.resolve())
        if any(ch in s for ch in "\x00|\n\r"):
            raise RuntimeError(
                f"sibling base path contains a reserved character "
                f"(NUL, |, newline, CR) — cannot encode safely: {s!r}\n"
                f"Recovery: rename the sibling directory to remove the "
                f"character, update harness.yaml.sibling_repos, then re-run."
            )
        sibling_strs.append(s)
    sibling_str = "|".join(sibling_strs)
    # PLAN-worktree-cross-session-data-loss-defense ADR-004: session_uuid is
    # NEW (Phase 3). When caller doesn't supply it, fall back to the current
    # process's UUID so wrap-up writers always set it. Legacy ref-files
    # (written by pre-Phase-3 finalize) lack this field → migration path
    # in _cli_post_commit_pop treats them as `legacy` sentinel for one shot.
    # PLAN-worktree-cross-session-data-loss-defense ADR-004 §2 (dirname embed):
    # extract UUID from wt_name (the durable create→finalize binding) instead
    # of calling `_current_session_uuid(base)` (REVIEW round 1 P0-MAN2 — that
    # helper returned shared per-project UUID, defeating cross-session
    # isolation). A legacy bare-timestamp `wt_name` (pre-dirname-embed) gets an
    # EMPTY session_uuid so the ref falls through to `post-commit-pop`'s
    # marker-present fallback — its old (pre-Layer3-per-session) behavior, where
    # the owner pops its own stash by marker. PLAN-layer3-per-session-ownership
    # REVIEW P1: the prior `_current_session_uuid` fallback wrote a NON-empty uuid
    # that `wt-uuid` (empty on a bare-timestamp name) could never reproduce into
    # the crumb, so the new strict guard stranded a legacy owner's OWN stash.
    # Standard `execute-<uuid>-<ts>` names still derive a non-empty uuid (the
    # writer-uuid-proof test pins this) — only genuine pre-upgrade refs change.
    dirname_uuid = _extract_uuid_from_wt_name(wt_name)
    effective_uuid = session_uuid or dirname_uuid
    body = (
        f"ref_sha: {ref_sha}\n"
        f"base: {base.resolve()}\n"
        f"session_marker: {session_marker_path.resolve()}\n"
        f"sibling_bases: {sibling_str}\n"
        f"session_uuid: {effective_uuid}\n"
        f"created_at: {datetime.now(UTC).isoformat()}\n"
    )
    atomic_write(path, body)
    _ensure_gitignore_entry(base, _STASH_REF_GITIGNORE_PATTERN)
    return path


def _read_stash_ref_file(path: Path) -> dict[str, str]:
    """Parse the 4-line key:value format. Returns {} on parse failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _is_git_repo(path: Path) -> bool:
    """Canonical check: ``git rev-parse --git-dir`` succeeds when cwd is a
    git working tree.

    Cheaper substitutes (`(path / ".git").exists()` or `.is_dir()`) accept a
    PLANTED regular file as a fake `.git` — REVIEW round 3 P1 surfaced this
    as an injection vector. Trusting git's own resolver is the authoritative
    answer that handles all four legitimate forms: normal `.git/` directory,
    worktree `.git` file containing `gitdir: ...`, bare repos, and submodule
    gitdir links.
    """
    if not path.is_dir():
        return False
    try:
        _run(["git", "rev-parse", "--git-dir"], cwd=path)
    except RuntimeError:
        return False
    return True


def _is_safe_absolute_path(value: str) -> bool:
    """Common safety predicate for ref-file path fields.

    Returns True iff value: starts with `/`, contains no NUL byte, normalizes
    consistently (no `.` / `..` segments after normalization), and is not a
    symlink. All filesystem stat calls are wrapped — `OSError` (e.g. embedded
    NUL → ValueError on POSIX) returns False, never raises (REVIEW round 3 P1:
    NUL-byte injection must not crash validation).
    """
    if not value or not value.startswith("/"):
        return False
    # POSIX "//" prefix is implementation-defined; on Linux `pathlib`
    # preserves it (`str(Path("//foo"))` == `"//foo"`), letting a crafted
    # double-slash path slip past downstream `Path(...)` normalization.
    # Reject explicitly (REVIEW round 5 P2 defense-in-depth).
    if value.startswith("//"):
        return False
    # Forbidden characters: NUL (crashes os.stat with ValueError on POSIX);
    # `|` (reserved as sibling_bases delimiter); `\n` and `\r` (would inject
    # extra `key: value` lines into the ref-file body and bypass validation
    # of injected keys — REVIEW round 4 P1: newline-in-path → ref body
    # injection). Any path containing these is rejected regardless of
    # whether the OS technically allows the character.
    if any(ch in value for ch in "\x00|\n\r"):
        return False
    try:
        p = Path(value)
        # Reject both `..` AND `.` segments explicitly (not relying on the
        # normalization check below as the sole gate — REVIEW round 4 P2).
        if any(part in {".", ".."} for part in p.parts):
            return False
        norm = str(p)
        if norm != value.rstrip("/") and norm + "/" != value:
            return False
        if p.is_symlink():
            return False
    except (OSError, ValueError):
        return False
    return True


def _validate_stash_ref_fields(fields: dict[str, str]) -> dict[str, str] | None:
    """ADR-002 + REVIEW round 3 hardening: validate ref-file fields before any
    filesystem op.

    Rejects (returns None) any of:
    - ``ref_sha`` not a 40-char lowercase hex string
    - ``base`` not absolute, contains ``..``, fails normalization, has NUL
      byte, or is a symlink
    - ``session_marker`` not matching the harness pattern, fails the same
      path-safety predicate, or is a symlink
    - ``sibling_bases`` (pipe (``|``)-separated absolute paths): any token
      fails ``_is_safe_absolute_path``
    - ``created_at`` empty or not ISO 8601 parseable

    On success returns the dict unchanged so callers can use validated values.
    Never raises — even adversarial NUL-byte content returns clean None
    (REVIEW round 3 P0: discovery + crash).
    """
    try:
        ref_sha = fields.get("ref_sha", "")
        if not _SHA_RE.match(ref_sha):
            return None

        base_str = fields.get("base", "")
        if not _is_safe_absolute_path(base_str):
            return None

        session_marker_str = fields.get("session_marker", "")
        if not _SESSION_MARKER_RE.match(session_marker_str):
            return None
        if not _is_safe_absolute_path(session_marker_str):
            return None

        # PLAN-worktree-cross-session-data-loss-defense ADR-004: session_uuid
        # is OPTIONAL for legacy ref files written before Phase 3. Missing →
        # REVIEW round 1 P1-CON1 fix: REJECT `legacy` as a value (the
        # supposedly-"one-shot" sentinel migration was never implemented
        # → permanent bypass forgery vector). Legacy ref files (lacking
        # `session_uuid` entirely) still pass through with empty string;
        # post-commit-pop's check distinguishes empty (legacy, ALLOWED for
        # one-shot processing via the marker-exists path) from explicit
        # "legacy" (REJECTED — must not be writable by anyone).
        session_uuid_str = fields.get("session_uuid", "")
        if session_uuid_str and not re.fullmatch(r"[0-9a-f]{12}", session_uuid_str):
            return None

        # sibling_bases is OPTIONAL (only the primary's ref writes it).
        # Encoding is pipe (`|`)-separated to keep the value within one
        # line of the `key: value` body (multi-line values would break the
        # parser). `|` is legal in POSIX paths but extraordinarily rare,
        # and `_is_safe_absolute_path` rejects any token containing `|`,
        # `\n`, `\r`, or NUL — closing newline-injection and ambiguous-
        # split vectors at validation time. Comma was considered and
        # rejected because comma is more common in POSIX paths than `|`.
        sibling_bases_raw = fields.get("sibling_bases", "")
        if sibling_bases_raw:
            for token in sibling_bases_raw.split("|"):
                t = token.strip()
                if t and not _is_safe_absolute_path(t):
                    return None

        # `created_at` is REQUIRED — empty fails validation (forensic anchor).
        created_at = fields.get("created_at", "")
        if not created_at:
            return None
        try:
            datetime.fromisoformat(created_at)
        except ValueError:
            return None
    except (OSError, ValueError):
        # Defense-in-depth: any unexpected OS-level path error becomes clean
        # rejection rather than uncaught propagation (REVIEW round 3 P1).
        return None

    return fields


def _session_marker_present(session_marker_path: str) -> bool:
    """True iff the absolute marker path resolves to a real file.

    Caller passes the validated absolute path from the ref file. A live marker
    means the wrapup invocation belongs to the same session that created the
    stash; an absent marker = stale (don't pop, REVIEW M-P1-2 + parent ADR-006).
    """
    return Path(session_marker_path).is_file()


def merge(wt_path: Path, strategy: str = "squash", commit: bool = True) -> None:
    """Merge the worktree's branch back into the base repo's current branch.

    Switches into the base repo and runs `git merge <branch>` with the
    requested strategy. Caller is responsible for choosing when to call this
    (typically: post-success, before cleanup).

    When ``commit=False`` and ``strategy="squash"``, the merge stages changes
    onto the base branch but does NOT auto-commit — wrapup is expected to
    create the user-facing commit (with proper message + Co-Authored-By).
    """
    wt = wt_path.resolve()
    base = wt.parent.parent
    branch = wt.name  # branch name == worktree directory basename (see create())
    args = ["git", "merge"]
    if strategy == "squash":
        args.extend(["--squash", branch])
        _run(args, cwd=base)
        if commit:
            # `--squash` stages but does not commit; finalize so the merge is durable.
            _run(
                ["git", "commit", "-m", f"squash-merge worktree {branch}"],
                cwd=base,
            )
    else:
        args.extend([f"--{strategy}", branch] if strategy != "merge" else [branch])
        _run(args, cwd=base)


# PLAN-untested-trio-fix ADR-002 + ADR-004: owned-prefix set for cleanup safety.
# cleanup_all must not touch worktrees created by other tools (e.g. Cursor IDE's
# /worktree command) that happen to share the same `.worktrees/` parent dir.
# Adding a new stage prefix requires updating this tuple (accepted manual-update
# risk per ADR-002; sentinel test rejected as tautological in PLAN R3).
_OWNED_PREFIXES: tuple[str, ...] = ("execute-", "plan-", "phase-", "autoloop-")


@dataclass
class PruneReport:
    """Summary of a stale harness-artifact prune pass."""

    removed_markers: list[Path] = field(default_factory=list)
    removed_worktrees: list[Path] = field(default_factory=list)
    removed_stash_refs: list[Path] = field(default_factory=list)
    preserved_stash_refs: list[tuple[Path, str]] = field(default_factory=list)
    removed_branches: list[str] = field(default_factory=list)
    preserved_branches: list[tuple[str, str]] = field(default_factory=list)
    # PLAN-worktree-deliverable-blocks-create ADR-004: orphan landed-marker refs
    # (branch gone) reaped this pass — so refs/hm-landed/* can't accumulate.
    removed_landed_markers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _list_worktrees(base_dir: Path) -> list[Path]:
    """Return absolute paths of harness-maker-owned worktrees under base_dir/.worktrees/.

    Uses `git worktree list --porcelain` so we don't depend on directory
    enumeration and naturally skip the main worktree. Filters by
    `_OWNED_PREFIXES` so cleanup_all does not affect cross-tool worktrees
    (PLAN-untested-trio-fix ADR-002).
    """
    base = base_dir.resolve()
    cp = _run(["git", "worktree", "list", "--porcelain"], cwd=base)
    paths: list[Path] = []
    main_path = base
    for line in cp.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        p = Path(line[len("worktree ") :]).resolve()
        if p == main_path:
            continue
        # Restrict to ones under base/.worktrees/ — leave external worktrees alone.
        if not (WORKTREE_DIR_NAME in p.parts and p.is_relative_to(base)):
            continue
        # Restrict to owned prefixes — leave other tools' worktrees alone.
        if not p.name.startswith(_OWNED_PREFIXES):
            continue
        paths.append(p)
    return paths


def _registered_worktree_paths(base_dir: Path) -> set[Path]:
    """Return every git-registered worktree path for ``base_dir``."""
    base = base_dir.resolve()
    try:
        cp = _run(["git", "worktree", "list", "--porcelain"], cwd=base)
    except RuntimeError:
        return set()
    out: set[Path] = set()
    for line in cp.stdout.splitlines():
        if line.startswith("worktree "):
            out.add(Path(line[len("worktree ") :]).resolve())
    return out


def _marker_referenced_paths(marker: Path) -> list[Path]:
    """Read absolute paths listed in a loop marker; invalid markers return [].

    Uses the shared ``parse_marker_paths`` so all four marker readers apply ONE
    header-skip rule (``startswith("/")``) — no per-reader drift if the content
    schema changes (PLAN-loop-marker-session-scoping, validator W1).
    """
    from harness_maker.loop_marker import parse_marker_paths

    try:
        text = marker.read_text(encoding="utf-8")
    except OSError:
        return []
    return [Path(p).resolve() for p in parse_marker_paths(text)]


def _marker_has_pending_stash(marker: Path) -> bool:
    """True iff a pending finalize-stash ref points its ``session_marker`` at this
    marker (ADR-003 — prune-create race).

    Matched by the ref's ``session_marker`` CONTENT field (not a filename stem):
    a multi-repo SIBLING-only stash is named ``.hm-finalize-stash-<primary>-<slug>``
    yet its ``session_marker`` points at the PRIMARY marker — the marker
    ``post-commit-pop`` keys on. Such a marker MUST survive prune so the deferred
    base-dirty stash can still be restored (else it is permanently stranded).
    """
    target = marker.resolve()
    for ref_file in marker.parent.glob(f"{_STASH_REF_PREFIX}*"):
        fields = _validate_stash_ref_fields(_read_stash_ref_file(ref_file))
        if fields is None:
            continue
        with contextlib.suppress(OSError, RuntimeError):
            if Path(fields["session_marker"]).resolve() != target:
                continue
            # REVIEW Codex P2: only a LIVE stash immortalizes the marker. A ref
            # whose stash object is gone OR whose content is already in HEAD is
            # itself drainable (same liveness test as the stash-ref drain below) —
            # preserving the marker for a DEAD ref would deadlock both forever
            # (marker kept ⇒ ref-drain skips it ⇒ marker kept …).
            ref_base = Path(fields["base"])
            ref_sha = fields["ref_sha"]
            if _stash_object_exists(ref_base, ref_sha) and not _stash_content_in_head(
                ref_base, ref_sha
            ):
                return True
    return False


def _is_orphan_marker(marker: Path) -> bool:
    """A loop marker is stale iff all referenced worktree dirs are absent AND it
    has no pending finalize-stash ref (ADR-003: a marker whose stash
    ``post-commit-pop`` still needs is preserved, not pruned)."""
    refs = _marker_referenced_paths(marker)
    if not (bool(refs) and not any(p.exists() for p in refs)):
        return False
    return not _marker_has_pending_stash(marker)


def _live_marker_references(base: Path) -> set[Path]:
    """Return worktree paths referenced by non-orphan marker files."""
    claude_dir = base / _LOOP_MARKER_DIR
    refs: set[Path] = set()
    if not claude_dir.is_dir():
        return refs
    for marker in claude_dir.glob(f"{_LOOP_MARKER_PREFIX}*"):
        marker_refs = _marker_referenced_paths(marker)
        if any(p.exists() for p in marker_refs):
            refs.update(marker_refs)
    return refs


def _git_expire_arg(grace_s: int) -> str:
    """git approxidate for `worktree prune --expire` keeping entries younger than
    grace_s seconds (ADR-002). Entries OLDER than the cutoff are de-registered."""
    return f"{grace_s}.seconds.ago"


def _reservation_path(base: Path, name: str) -> Path:
    """The pre-create reservation file for worktree ``name`` (ADR-001)."""
    return base.resolve() / _LOOP_MARKER_DIR / f".hm-creating-{name}"


def _any_fresh_reservation(base: Path) -> bool:
    """True iff ANY peer `create()` is mid-flight (a fresh `.hm-creating-*`).

    Used to defer `git worktree prune` while a peer is inside `git worktree add`:
    pruning then would remove the peer's HALF-WRITTEN `.git/worktrees/<name>/`
    admin entry (its `gitdir` not yet written) regardless of `--expire`, crashing
    the peer's add. Deferring is brief (the reservation clears on create completion).
    """
    claude_dir = base.resolve() / _LOOP_MARKER_DIR
    if not claude_dir.is_dir():
        return False
    cutoff = time.time() - _PRUNE_GRACE_SECONDS
    for reservation in claude_dir.glob(".hm-creating-*"):
        with contextlib.suppress(OSError):
            if reservation.stat().st_mtime >= cutoff:
                return True
    return False


def _has_fresh_reservation(base: Path, wt_dir: Path) -> bool:
    """True iff a peer's in-flight `create()` reserved ``wt_dir`` < grace ago.

    The reservation file's mtime is the create-START time (written once before
    ``git worktree add``), so it is a reliable freshness signal — unlike the leaf
    dir's own mtime, which goes stale during a nested checkout (Codex). PURE
    predicate — reaping an aged/leaked reservation is the separate
    ``_reap_aged_reservations`` step (REVIEW P2: no hidden mutation in a boolean,
    no stat-then-unlink race against a name-colliding peer's fresh re-write).
    """
    reservation = _reservation_path(base, wt_dir.name)
    try:
        age = time.time() - reservation.stat().st_mtime
    except OSError:
        return False  # no reservation (or vanished) → not protected
    return age <= _PRUNE_GRACE_SECONDS


def _reap_aged_reservations(base: Path) -> None:
    """Remove leaked aged ``.hm-creating-*`` reservations (a create SIGKILL'd before
    its ``finally`` ran). Only reaps entries older than the grace — never a live
    create's; a name-colliding peer's fresh re-write (negligible uuid+timestamp
    collision) is spared by the ``< cutoff`` gate on the just-read mtime."""
    claude_dir = base.resolve() / _LOOP_MARKER_DIR
    if not claude_dir.is_dir():
        return
    cutoff = time.time() - _PRUNE_GRACE_SECONDS
    for reservation in claude_dir.glob(".hm-creating-*"):
        with contextlib.suppress(OSError):
            if reservation.stat().st_mtime < cutoff:
                reservation.unlink(missing_ok=True)


def _scan_dangling_worktrees(base_dir: Path) -> list[Path]:
    """Owned ``.worktrees/*`` dirs absent from git registration and live markers.

    ADR-001 (prune-create race): additionally never reap a dir that (a) has a
    FRESH pre-create reservation (a peer's in-flight `create()`) or (b) has no
    ``.git`` entry (a random non-worktree dir, or an incomplete add) — both are
    biased-to-preserve filters that close the work-loss window.
    """
    base = base_dir.resolve()
    worktrees_dir = base / WORKTREE_DIR_NAME
    if not worktrees_dir.is_dir():
        return []
    registered = _registered_worktree_paths(base)
    live_refs = _live_marker_references(base)
    dangling: list[Path] = []
    for candidate in worktrees_dir.iterdir():
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if not candidate.name.startswith(_OWNED_PREFIXES):
            continue
        if resolved in registered or resolved in live_refs:
            continue
        if _has_fresh_reservation(base, candidate):
            continue  # a peer's in-flight create() — never rmtree it
        if not (candidate / ".git").exists():
            continue  # not a worktree (or pre-`.git` incomplete add) — preserve
        dangling.append(resolved)
    return dangling


def _git_blob_sha(repo: Path, rev: str, path: str) -> str | None:
    """Return blob SHA for ``rev:path`` or None when the path is absent."""
    try:
        cp = _run(["git", "rev-parse", f"{rev}:{path}"], cwd=repo)
    except RuntimeError:
        return None
    sha = cp.stdout.strip()
    return sha if _SHA_RE.match(sha) else None


def _stash_has_third_parent(base: Path, ref_sha: str) -> bool:
    try:
        _run(["git", "rev-parse", "--verify", f"{ref_sha}^3^{{tree}}"], cwd=base)
    except RuntimeError:
        return False
    return True


def _stash_object_exists(base: Path, ref_sha: str) -> bool:
    """True iff the stash commit object is still resolvable in the object DB.

    PLAN-worktree-base-artifact-pollution ADR-005. A merely *dropped* stash is
    still reachable via the reflog, so `git cat-file -e <sha>^{commit}`
    SUCCEEDS in that window and this returns True — the ref must be PRESERVED
    (the work is recoverable). It returns False only once the object is truly
    gone (gc-pruned or never existed), at which point the ref file is pure
    cruft and is safe to drain (there is nothing left to restore).
    """
    try:
        _run(["git", "cat-file", "-e", f"{ref_sha}^{{commit}}"], cwd=base)
    except RuntimeError:
        return False
    return True


def _stash_content_in_head(base_dir: Path, ref_sha: str) -> bool:
    """True iff every tracked and untracked stash blob already exists in HEAD.

    The predicate is HEAD-relative and covers the stash's optional untracked
    tree (``S^3``). Missing in HEAD means preserve the ref; cleanup must bias
    toward retention when uncertain.
    """
    base = base_dir.resolve()
    try:
        _run(["git", "cat-file", "-e", f"{ref_sha}^{{commit}}"], cwd=base)
    except RuntimeError:
        return False

    try:
        tracked = _run(
            ["git", "diff", "--name-only", f"{ref_sha}^1", ref_sha],
            cwd=base,
        )
    except RuntimeError:
        return False
    for path in [p for p in tracked.stdout.splitlines() if p.strip()]:
        stash_blob = _git_blob_sha(base, ref_sha, path)
        head_blob = _git_blob_sha(base, "HEAD", path)
        if stash_blob != head_blob:
            return False

    if not _stash_has_third_parent(base, ref_sha):
        return True
    try:
        untracked = _run(["git", "ls-tree", "-r", f"{ref_sha}^3"], cwd=base)
    except RuntimeError:
        return False
    for line in untracked.stdout.splitlines():
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        stash_blob = parts[2]
        head_blob = _git_blob_sha(base, "HEAD", path)
        if stash_blob != head_blob:
            return False
    return True


def _branch_content_in_head(base_dir: Path, branch: str) -> bool:
    """True iff every blob the branch changed since its merge-base with HEAD is
    already byte-identical in HEAD.

    Mirrors `_stash_content_in_head` (PLAN-p6-p7-worktree-finalize ADR-002): a
    *squash-merged* branch tip is NOT a HEAD ancestor, so `git branch --merged`
    would wrongly report it unmerged. We compare content, not ancestry. Biased
    toward preserve — any unresolvable ref, missing, or mismatched blob returns
    False so the orphan-branch sweep keeps the branch.

    Unlike the stash predicate there is NO untracked-tree (``S^3``) leg: a
    branch has no untracked tree — the worktree's untracked/uncommitted work is
    captured into the ``wip(execute)`` commit before any cleanup, so the
    merge-base diff below already enumerates it as tracked changes.
    """
    base = base_dir.resolve()
    try:
        _run(["git", "rev-parse", "--verify", f"{branch}^{{commit}}"], cwd=base)
    except RuntimeError:
        return False
    try:
        mb = _run(["git", "merge-base", branch, "HEAD"], cwd=base)
    except RuntimeError:
        return False
    merge_base = mb.stdout.strip()
    if not _SHA_RE.match(merge_base):
        return False
    try:
        changed = _run(["git", "diff", "--name-only", merge_base, branch], cwd=base)
    except RuntimeError:
        return False
    for path in [p for p in changed.stdout.splitlines() if p.strip()]:
        if _git_blob_sha(base, branch, path) != _git_blob_sha(base, "HEAD", path):
            return False
    return True


def _list_owned_branches(base_dir: Path) -> list[str]:
    """Owned-prefix local branches. Branch name == worktree dir name (created
    via `git worktree add -b <name>`), so `_OWNED_PREFIXES` is the single source
    of truth for both — no separate branch-prefix constant (drift risk)."""
    base = base_dir.resolve()
    try:
        cp = _run(
            ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
            cwd=base,
        )
    except RuntimeError:
        return []
    return [b.strip() for b in cp.stdout.splitlines() if b.strip().startswith(_OWNED_PREFIXES)]


# PLAN-worktree-deliverable-blocks-create ADR-003 — landed marker.
# A git ref `refs/hm-landed/v1/<branch>` records the branch TIP at finalize
# success. prune_stale deletes a markered branch iff its tip still equals this
# SHA (survives later HEAD edits without a content re-compare; name-collision
# safe — a re-created same-named branch has a different tip). Refs are not
# work-tree files → zero gitignore churn. The `v1/` namespace allows a future
# format migration.
_LANDED_REF_PREFIX = "refs/hm-landed/v1/"


def _landed_ref_name(branch: str) -> str:
    return f"{_LANDED_REF_PREFIX}{branch}"


def _branch_tip(base: Path, branch: str) -> str | None:
    """Return the 40-hex tip commit of branch, or None if it doesn't resolve."""
    try:
        cp = _run(["git", "rev-parse", "--verify", f"{branch}^{{commit}}"], cwd=base)
    except RuntimeError:
        return None
    sha = cp.stdout.strip()
    return sha if _SHA_RE.match(sha) else None


def _branch_tip_message(base: Path, branch: str) -> str | None:
    """Return branch's tip commit message (full subject + body), or None.

    The squash-land defaults to this so the user's curated wrapup commit — its
    why-focused subject/body AND the `Co-Authored-By` trailer — survives onto the
    base branch instead of a generic `chore(...): squash-land` placeholder
    (REVIEW-2026-06-21 P2-3). Computed BEFORE the fence/`_capture_pending_in_worktree`
    so the tip is the wrapup Step-7 commit, not a later `wip(execute): capture`.
    Returns None on git failure or an empty message so the caller can fall back."""
    try:
        msg = _run(["git", "log", "-1", "--format=%B", branch], cwd=base).stdout.strip()
    except RuntimeError:
        return None
    return msg or None


def _write_landed_marker(base: Path, branch: str) -> None:
    """Record branch's tip SHA as its landed marker (atomic `git update-ref`)."""
    tip = _branch_tip(base, branch)
    if tip is None:
        raise RuntimeError(f"cannot resolve tip of branch {branch!r} for landed marker")
    _run(["git", "update-ref", _landed_ref_name(branch), tip], cwd=base)


def _read_landed_marker(base: Path, branch: str) -> str | None:
    """Return the recorded landed tip SHA for branch, or None if no marker."""
    try:
        sha = _run(
            ["git", "rev-parse", "--verify", _landed_ref_name(branch)], cwd=base
        ).stdout.strip()
    except RuntimeError:
        return None
    return sha if _SHA_RE.match(sha) else None


def _delete_landed_marker(base: Path, branch: str) -> None:
    """Best-effort delete of branch's landed marker ref."""
    with contextlib.suppress(RuntimeError):
        _run(["git", "update-ref", "-d", _landed_ref_name(branch)], cwd=base)


def _list_landed_markers(base: Path) -> list[str]:
    """Return branch names that currently carry a landed marker."""
    try:
        cp = _run(["git", "for-each-ref", "--format=%(refname)", _LANDED_REF_PREFIX], cwd=base)
    except RuntimeError:
        return []
    out: list[str] = []
    for line in cp.stdout.splitlines():
        ref = line.strip()
        if ref.startswith(_LANDED_REF_PREFIX):
            out.append(ref[len(_LANDED_REF_PREFIX) :])
    return out


def prune_stale(base_dir: Path, *, dry_run: bool = False) -> PruneReport:
    """Prune stale harness-owned markers, dangling worktrees, and safe refs.

    Destructive actions are restricted by owned prefixes and orphan checks.
    Stash refs are deleted only when their tracked and untracked content is
    already present in HEAD; otherwise they are preserved with a warning.
    """
    import shutil

    base = base_dir.resolve()
    report = PruneReport()
    with contextlib.suppress(RuntimeError):
        # ADR-002: defer `git worktree prune` while a peer is mid-create — pruning
        # then would remove the peer's half-written admin entry (`gitdir` not yet
        # present) regardless of `--expire`, crashing its `git worktree add`
        # (discovered by the Phase 4 concurrent test). `--expire` additionally
        # spares a peer's RECENT COMPLETE admin entry; on an `--expire`-rejecting
        # git the suppressed RuntimeError SKIPS the prune (never a bare prune,
        # which would re-open the de-registration race).
        if not dry_run and not _any_fresh_reservation(base):
            _run(
                ["git", "worktree", "prune", f"--expire={_git_expire_arg(_PRUNE_GRACE_SECONDS)}"],
                cwd=base,
            )

    if not dry_run:
        _reap_aged_reservations(base)

    claude_dir = base / _LOOP_MARKER_DIR
    if claude_dir.is_dir():
        for marker in sorted(claude_dir.glob(f"{_LOOP_MARKER_PREFIX}*")):
            if not _is_orphan_marker(marker):
                continue
            report.removed_markers.append(marker)
            if not dry_run:
                marker.unlink(missing_ok=True)

    for wt in _scan_dangling_worktrees(base):
        report.removed_worktrees.append(wt)
        if not dry_run:
            shutil.rmtree(wt, ignore_errors=True)

    # Orphan worktree-branch sweep (PLAN-p6-p7-worktree-finalize ADR-002).
    # `cleanup()` never runs `git branch -D` — it must preserve the
    # `wip(execute)` recovery net while a worktree is live — so squash-merged
    # branches leak forever. Here, at create-time prune, sweep an owned-prefix
    # branch whose worktree dir is GONE, but ONLY when its content is already in
    # HEAD (content-gated, biased-to-preserve). The recovery net is intact: a
    # branch with work not yet in HEAD is preserved + warned, never deleted.
    # Live-skip keyed on git REGISTRATION (ADR-002), not mere dir presence: a
    # registered-but-dir-missing worktree still has the branch checked out, so a
    # `git branch -D` would refuse anyway — skip it cleanly up front. `dir.exists()`
    # stays as a belt-and-suspenders second signal.
    registered = _registered_worktree_paths(base)
    for branch in _list_owned_branches(base):
        wt_dir = (base / WORKTREE_DIR_NAME / branch).resolve()
        if wt_dir in registered or wt_dir.exists():
            continue  # live worktree — never sweep its branch
        # PLAN-worktree-deliverable-blocks-create ADR-003: a landed marker whose
        # SHA still equals the branch tip proves THIS branch was squash-merged at
        # finalize — delete unconditionally, no content re-compare (survives
        # later HEAD edits). A stale/collision marker (tip moved on) does NOT
        # match → fall through to the preserve-biased content-gate.
        marker_sha = _read_landed_marker(base, branch)
        landed_by_marker = marker_sha is not None and marker_sha == _branch_tip(base, branch)
        if not landed_by_marker and not _branch_content_in_head(base, branch):
            hint = (
                f"preserved branch {branch}: content not fully present in HEAD; "
                f"inspect with `git log -p {branch}` before deleting"
            )
            report.preserved_branches.append((branch, hint))
            report.warnings.append(hint)
            continue
        if dry_run:
            report.removed_branches.append(branch)
            continue
        # Append only on a confirmed delete — never claim a removal that did not
        # happen (e.g. a branch still checked out in a registration we did not
        # skip). A failed delete is reported honestly instead.
        try:
            _run(["git", "branch", "-D", branch], cwd=base)
        except RuntimeError as exc:
            warn = f"branch sweep: `git branch -D {branch}` failed ({exc}); left in place"
            report.preserved_branches.append((branch, warn))
            report.warnings.append(warn)
            continue
        # ADR-004: drop the landed marker in the SAME op as its branch so
        # refs/hm-landed/* never outlives the branch it points at.
        _delete_landed_marker(base, branch)
        report.removed_branches.append(branch)

    # ADR-004 orphan reaping: any landed marker whose branch no longer exists
    # (deleted externally or in a prior run) is pure cruft — reap it so the ref
    # namespace cannot accumulate the way the branches did.
    existing_branches = set(_list_owned_branches(base))
    for marker_branch in _list_landed_markers(base):
        if marker_branch in existing_branches:
            continue
        report.removed_landed_markers.append(marker_branch)
        if not dry_run:
            _delete_landed_marker(base, marker_branch)

    if claude_dir.is_dir():
        for ref_file in sorted(claude_dir.glob(f"{_STASH_REF_PREFIX}*")):
            fields = _validate_stash_ref_fields(_read_stash_ref_file(ref_file))
            if fields is None:
                continue
            wt_name = ref_file.name[len(_STASH_REF_PREFIX) :]
            wt_dir = base / WORKTREE_DIR_NAME / wt_name
            if wt_dir.exists() or _session_marker_present(fields["session_marker"]):
                continue
            ref_sha = fields["ref_sha"]
            ref_base = Path(fields["base"]).resolve()
            # The recorded base repo can be gone (e.g. a removed sibling repo).
            # `_run` would raise FileNotFoundError on a non-existent cwd — which
            # neither `_run` nor `_stash_object_exists` catches — so guard here.
            # A gone base means the stash object is unreachable → pure cruft → drain.
            if not ref_base.is_dir():
                report.removed_stash_refs.append(ref_file)
                if not dry_run:
                    ref_file.unlink(missing_ok=True)
                continue
            # ADR-005: a ref whose stash object is truly gone (gc-pruned or
            # never existed) is pure cruft — nothing to restore — so drain it.
            # This is NOT a `git stash drop` (no object to drop), so the
            # ADR-008 "never drop without diff preview" contract is untouched.
            # Otherwise fall back to the content-in-HEAD test; only a resolvable
            # stash whose content is NOT yet in HEAD is preserved + warned.
            if not _stash_object_exists(ref_base, ref_sha) or _stash_content_in_head(
                ref_base, ref_sha
            ):
                report.removed_stash_refs.append(ref_file)
                if not dry_run:
                    ref_file.unlink(missing_ok=True)
            else:
                hint = (
                    f"preserved {ref_file.name}: stash content not fully present in HEAD; "
                    f"inspect with `git stash show -p --include-untracked {ref_sha}`"
                )
                report.preserved_stash_refs.append((ref_file, hint))
                report.warnings.append(hint)
    return report


def cleanup_all(base_dir: Path, force: bool = False) -> int:
    """Remove every worktree under base_dir/.worktrees/. Returns the count removed."""
    base = base_dir.resolve()
    removed = 0
    for wt in _list_worktrees(base):
        args = ["git", "worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(wt))
        try:
            _run(args, cwd=base)
            removed += 1
        except RuntimeError:
            # Continue with the rest; a single dirty worktree shouldn't block
            # the autoloop blocker recovery path.
            continue
    return removed


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry — invoked by slash commands as `python -m harness_maker.worktree`
# so /hm:execute can engage isolation deterministically (PLAN-cursor-rootcause
# R2: stop relying on Cursor skill auto-discovery for safety-critical ops).
# ──────────────────────────────────────────────────────────────────────────────


_SIBLING_SENTINEL = "SIBLING_WORKTREE_PATHS"
_EXECUTE_MD_REL = Path(".claude") / "commands" / "hm" / "execute.md"


def _load_sibling_dirs(harness_yaml: Path, base: Path) -> list[Path]:
    """Read sibling_repos from harness.yaml; resolve relative paths against base.

    REVIEW round 2 hardening (P1: path traversal): each resolved path is gated by
    (a) existence as a directory and (b) presence of a ``.git`` entry (file or
    dir). Adversarial or typo'd entries like ``../../etc/secrets`` or absolute
    non-repo paths are silently dropped with a stderr warning. Entries pointing
    back at the primary base are deduplicated by callers (`bases_to_scan` uses
    dict.fromkeys to preserve order while removing dupes).
    """
    try:
        data = load_harness_yaml(harness_yaml)
    except (OSError, yaml.YAMLError):
        return []
    raw = data.get("sibling_repos")
    if not isinstance(raw, list):
        return []

    resolved: list[Path] = []
    for rel in raw:
        if not isinstance(rel, str):
            continue
        candidate = (base / rel).resolve()
        # Containment via canonical git check: catches path-traversal AND
        # planted `.git` files. REVIEW round 3 P1: `.exists()` accepted a
        # regular file at `<path>/.git` as proof of git-repo status, so we
        # now rely on `git rev-parse --git-dir` (the authoritative answer).
        if not _is_git_repo(candidate):
            print(
                f"[worktree] sibling_repos entry {rel!r} is not a git "
                f"working tree (git rev-parse failed); skipping — "
                f"path-traversal guard",
                file=sys.stderr,
            )
            continue
        resolved.append(candidate)
    return resolved


def _execute_md_has_sentinel(base: Path) -> bool:
    """Return True if the rendered execute.md contains the sibling sentinel."""
    md = base / _EXECUTE_MD_REL
    try:
        return _SIBLING_SENTINEL in md.read_text(encoding="utf-8")
    except OSError:
        return False


def _cli_create(args: list[str]) -> int:
    """`python -m harness_maker.worktree create <stage> <base_dir>` — print path or skip.

    Empty stdout (with exit 0) signals "scope check off, run in place" — the
    slash command treats an empty `worktree_path` as "no isolation needed".

    Idempotent: if ``base_dir`` (typically `$(pwd)`) is **already inside** a
    `.worktrees/<name>/` directory, return that worktree path without
    creating a new one. Lets `/hm:loop` engage worktree once at the top and
    have nested standalone `/hm:execute` invocations re-detect + reuse it
    instead of nesting worktrees.
    """
    # PLAN-worktree-cross-session-data-loss-defense ADR-002+003 escape flags:
    # parse before positional consumption.
    allow_stash_queue = "--allow-stash-queue" in args
    allow_dirty_base = "--allow-dirty-base" in args
    debug_worktree = "--debug-worktree" in args
    args = [
        a
        for a in args
        if a not in ("--allow-stash-queue", "--allow-dirty-base", "--debug-worktree")
    ]

    # PLAN-loop-marker-session-scoping ADR-002: optional value flag carrying the
    # Claude session id (from $HM_SESSION_ID) — recorded in marker content so the
    # Stop-hook can match it. Extract the flag + its value before the positional
    # count check. Absent → empty (back-compat; marker header empty).
    claude_session_id = ""
    # ADR-008: the loop signal is flag PRESENCE, never value truthiness. loop.md.j2
    # passes `--claude-session-id "$HM_SESSION_ID"` QUOTED, and in a degraded environment
    # (Cursor, Codex, or a SessionStart-hook failure — NOT "WSL2", which is what this
    # comment used to claim) the flag arrives with an EMPTY value. Selecting on the value
    # would label every such loop `hm:execute`, silently defeating the loop attribution
    # this exists for.
    #
    # PRESENCE-overloading is therefore load-bearing and CONSTRAINS callers: no other
    # `worktree create` call site may pass this flag, or its spans get stamped `hm:loop`
    # and its marker gains a session header the Stop-hook will content-match — blocking a
    # standalone `/hm:execute` from ever stopping (PLAN-sessionid-env-propagation ADR-007,
    # risk R9; guarded by tests/render/test_render_sessionid_wiring.py).
    is_loop_create = "--claude-session-id" in args
    if is_loop_create:
        idx = args.index("--claude-session-id")
        if idx + 1 >= len(args):
            print("create: --claude-session-id requires a value", file=sys.stderr)
            return 2
        claude_session_id = args[idx + 1]
        del args[idx : idx + 2]

    if len(args) != 2:
        print(
            "usage: create <stage> <base_dir> [--allow-stash-queue] "
            "[--allow-dirty-base] [--debug-worktree] [--claude-session-id <id>]",
            file=sys.stderr,
        )
        return 2
    stage, base_str = args
    base = Path(base_str).resolve()

    # ADR-008 loop coverage. `/hm:loop` orders its stages NOT to run task-preflight
    # (loop.md.j2), so the per-stage emitter never fires inside a loop; this is the
    # loop's own load-bearing call, so it carries the span instead.
    #
    # Emitted HERE — before the existing-worktree reuse return and before the scope
    # check — because a span records that a stage STARTED, not that a worktree was
    # created. `create` legitimately returns empty ("scope off, run in place") and
    # that run still spends tokens; emitting after the early return would have left
    # every no-isolation loop unattributed, which is the bucket this plan exists to
    # shrink. One `create` invocation ⇒ exactly one span, which is also what makes
    # it testable.
    #
    # Granularity is LOOP-level, not per-iteration: loop.md.j2 states "Per-loop (not
    # per-iter)" and calls `create` once at the top, so one span covers the whole
    # run and a long loop pushes the remainder into `capped_turns` — visible, but
    # not attributed. Per-iteration spans would mean redesigning the loop's
    # isolation (Non-Goal 1).
    #
    # `--claude-session-id` PRESENCE is the loop signal: CLAUDE.md records that ONLY
    # loop.md.j2 passes it, so a standalone /hm:execute create is not a loop. The
    # flag's VALUE is empty in any degraded environment (Cursor / Codex / a genuine
    # SessionStart-hook failure) and must not be used to decide this.
    _emit_stage_span(
        base,
        stage="hm:loop" if is_loop_create else f"hm:{stage}",
        claude_session_id=claude_session_id or None,
    )

    existing = _detect_existing_worktree(base)
    if existing is not None:
        # Already inside a worktree; marker should already be in place from
        # the parent loop's create. No-op idempotent return.
        print(str(existing))
        return 0

    # PLAN-worktree-base-artifact-pollution ADR-002: auto-migrate the user's
    # .gitignore to cover harness churn on every fresh create (idempotent +
    # subsumption-safe). Existing installs that pre-date the churn set pick
    # the patterns up here on their next create, so the base stops looking
    # dirty for parallel sessions. Runs AFTER the existing-worktree early
    # return (the nested-reuse path needs no migration) and BEFORE the guards.
    _ensure_harness_gitignore(base)

    # ADR-003 queue-guard (must run BEFORE scope check so a misconfigured
    # base still surfaces the guard message — failure mode visibility):
    claude_dir = base / _LOOP_MARKER_DIR
    if not debug_worktree:
        prune_report = prune_stale(base)
        _print_prune_warnings(prune_report)
    pending = _count_pending_stashes(claude_dir)
    # REVIEW round 1 P1-MAN4 fix: audit-log every bypass-flag use so post-
    # incident forensics can distinguish "guard never fired" from "guard
    # fired and was bypassed". Without this print, the 4th recurrence
    # (if any) would have no trace of which escape flag was used.
    if pending >= 2 and allow_stash_queue:
        print(
            f"[WARN] worktree create: --allow-stash-queue active — bypassing "
            f"queue-guard (pending={pending}). "
            f"PLAN-worktree-cross-session-data-loss-defense ADR-003 audit trail.",
            file=sys.stderr,
        )
    if pending >= 2 and not allow_stash_queue:
        ref_list = "\n  ".join(_list_pending_stash_refs(claude_dir))
        print(
            f"[ERROR] worktree create blocked — ≥2 unpopped finalize stashes "
            f"detected ({pending}):\n  {ref_list}\n\n"
            f"This is the canonical 'wrapup-not-run-between-exec-rev-turns' "
            f"signature. Run `/hm:wrapup` to drain each pending stash + ref, "
            f"OR pass `--allow-stash-queue` to bypass this guard.\n"
            f"\nWhy this guard exists: 2026-05-23 incident (3rd recurrence) "
            f"— PLAN-worktree-cross-session-data-loss-defense ADR-003.",
            file=sys.stderr,
        )
        return 1

    # ADR-002 dirty-base guard:
    # REVIEW round 1 P1-MAN4 fix: log bypass-flag use for audit.
    if allow_dirty_base and _has_user_dirty_state(base):
        print(
            "[WARN] worktree create: --allow-dirty-base active — bypassing "
            "dirty-base-guard. PLAN-worktree-cross-session-data-loss-defense "
            "ADR-002 audit trail.",
            file=sys.stderr,
        )
    if not allow_dirty_base and _has_user_dirty_state(base):
        dirty_list = "\n  ".join(_list_user_dirty_files(base))
        print(
            f"[ERROR] worktree create blocked — base repo has uncommitted user "
            f"changes:\n  {dirty_list}\n\n"
            f"`worktree finalize stage-only` would stash these into the same "
            f"queue as our own finalize stash, re-creating the cross-session "
            f"contamination pattern. Commit, stash, or pass `--allow-dirty-base` "
            f"to bypass this guard.\n"
            f"\nWhy this guard exists: PLAN-worktree-cross-session-data-loss-"
            f"defense ADR-002 ([fail:design] worktree-finalize-pulls-orphan-"
            f"wip-into-main count:2 → 3rd recurrence 2026-05-23).",
            file=sys.stderr,
        )
        return 1

    yaml_path = base / ".claude" / "harness.yaml"
    # PLAN-worktree-side-defaults R11: this gate used to read the retired
    # `worktree.scope` directly. The moment the preset templates stopped rendering
    # `scope`, that read returned False on a freshly-rendered **ON** harness, this
    # printed an empty line, and every rendered command reads empty output as "no
    # isolation; operate in cwd" — a total, silent isolation loss that no render or
    # unit test in the suite would have caught. Route through the single reader; the
    # `stage` argument survives so a legacy `scope` harness keeps per-stage behavior.
    if not worktree_enabled(base, stage=stage):
        print("")
        return 0

    # Load sibling_repos from harness.yaml (empty list when field absent)
    sibling_dirs = _load_sibling_dirs(yaml_path, base)

    wt_paths = create(
        stage,
        base,
        sibling_dirs=sibling_dirs if sibling_dirs else None,
        claude_session_id=claude_session_id,
    )

    # Stale execute.md detection: if sibling repos configured but execute.md
    # lacks the SIBLING_WORKTREE_PATHS sentinel, degrade to primary-only output
    # so the old prompt doesn't silently drop sibling isolation.
    if sibling_dirs and not _execute_md_has_sentinel(base):
        print(
            "[WARNING] execute.md is stale — run 'make --update' to enable "
            "sibling worktree support",
            file=sys.stderr,
        )
        # Gate already protects both WTs via .hm-loop-active; only stdout differs.
        print(str(wt_paths[0]))
        return 0

    for wt in wt_paths:
        print(str(wt))
    return 0


def _marker_path(project_root: Path, wt_name: str) -> Path:
    """Return the per-session marker file path for this worktree."""
    return project_root / _LOOP_MARKER_DIR / f"{_LOOP_MARKER_PREFIX}{wt_name}"


def _write_loop_marker(
    project_root: Path,
    wt_name: str,
    wt_paths: list[Path],
    claude_session_id: str = "",
) -> None:
    """Persist active-worktree paths for this session to a per-session marker file.

    File: ``.claude/.hm-loop-{wt_name}`` — one file per active session so
    parallel sessions coexist without overwriting each other (ADR-006). The
    filename stays worktree-keyed (``_owned_session_uuids`` reads the UUID from
    it — ADR-005); the Claude ``session_id`` is recorded in the CONTENT header
    so the Stop-hook can match it without renaming the file
    (PLAN-loop-marker-session-scoping ADR-002).

    Content: a ``claude_session_id:`` header line then newline-separated
    absolute paths (single-repo = one path, multi-repo = N).

    Atomic write — concurrent readers (gate hook) must never see partial.
    Also ensures ``.claude/.hm-loop-*`` is in ``.gitignore``.
    """
    from harness_maker.io_utils import atomic_write
    from harness_maker.loop_marker import format_marker_content

    marker = _marker_path(project_root, wt_name)
    content = format_marker_content(claude_session_id, wt_paths)
    atomic_write(marker, content)
    _ensure_gitignore_entry(project_root, _LOOP_MARKER_GITIGNORE_PATTERN)


def _clear_loop_marker(project_root: Path, wt_name: str) -> None:
    """Remove only this session's per-session marker file.

    Called when ALL repos for this session finalize successfully. Other
    parallel sessions' marker files are untouched (ADR-006).
    """
    _marker_path(project_root, wt_name).unlink(missing_ok=True)


def _read_active_worktrees(project_root: Path) -> list[Path]:
    """Return all active worktree paths across all sessions.

    Scans all ``.claude/.hm-loop-*`` files (one per parallel session),
    collects every path listed in them, and filters non-existent entries.
    Returns empty list when no marker files exist.
    """
    from harness_maker.loop_marker import parse_marker_paths

    marker_dir = project_root / _LOOP_MARKER_DIR
    paths: list[Path] = []
    try:
        marker_files = sorted(marker_dir.glob(f"{_LOOP_MARKER_PREFIX}*"))
    except OSError:
        return []
    for marker in marker_files:
        try:
            text = marker.read_text(encoding="utf-8")
        except OSError:
            continue
        # Drop the content header by the "/"-prefix rule (validator W1) — never
        # by existence, so a header line can't be mistaken for a worktree path.
        for stripped in parse_marker_paths(text):
            p = Path(stripped)
            if p.exists():
                paths.append(p)
    return paths


def _ensure_gitignore_entry(project_root: Path, entry: str) -> None:
    """Append ``entry`` to ``<project_root>/.gitignore`` if not already there.

    Cheap idempotent line-append:
    - File missing → create with the entry as sole content
    - File present, entry already (exact line match) → no-op
    - File present, entry semantically subsumed by broader pattern → no-op
      (e.g. `.claude/` covers `.claude/.hm-session-uuid`; check via
      `git check-ignore`). Without this guard, every test fixture or user
      who has `.claude/` ignored at the dir level gets a spurious
      `.claude/.hm-session-uuid` line appended on first session-uuid
      generation → `.gitignore` shows as `M` in status → trips
      `_stash_base_dirty` → ref file written → marker not cleared
      (fail mode reproduced in test_worktree_multi.py 2026-05-24).
    - File present, entry absent + not subsumed → append.

    Failures are silently swallowed: gitignore hygiene is best-effort, not
    a hard correctness requirement. The gate still works; users may have
    a marker to manually clean up if a loop crashes.
    """
    from harness_maker.io_utils import atomic_write

    gitignore = project_root / ".gitignore"
    try:
        if gitignore.is_file():
            existing = gitignore.read_text(encoding="utf-8")
            # Match by line — `.claude/.hm-loop-active` (avoid false-match of
            # a longer line that happens to start with our pattern).
            for line in existing.splitlines():
                if line.strip() == entry:
                    return
            # Semantic-subsumption check via git: if the entry-as-path is
            # already ignored by a broader pattern, skip the append. The
            # entry typically looks like `.claude/.hm-session-uuid` (path-like)
            # rather than a glob — `git check-ignore` correctly classifies
            # path-like entries. For glob entries (e.g. `.claude/.hm-loop-*`)
            # check-ignore returns non-zero on the glob string itself, so the
            # subsumption check only succeeds for path-shaped entries —
            # exactly the case where unnecessary appending is the bug.
            try:
                check = subprocess.run(  # noqa: S603
                    ["git", "check-ignore", "-q", "--", entry],
                    cwd=str(project_root),
                    capture_output=True,
                    timeout=5,
                )
                if check.returncode == 0:
                    return  # Already covered by existing pattern.
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                # Best-effort — fall through to append if check fails.
                pass
            sep = "" if existing.endswith("\n") else "\n"
            # Atomic-append: read full content + append entry + atomic_write
            # the whole file. Mirrors the new-file branch below and prevents
            # the SIGINT-leaves-partial-line failure mode (REVIEW M-P1-2).
            atomic_write(gitignore, f"{existing}{sep}{entry}\n")
        else:
            # Atomic write via tempfile + os.replace — CLAUDE.md project rule
            # forbids plain open(path, "w") outside tempfile-owned directories.
            from harness_maker.io_utils import atomic_write

            atomic_write(gitignore, f"{entry}\n")
    except OSError:
        # Best-effort; don't fail loop creation over a gitignore write.
        pass


def _ensure_gitignore_entries(project_root: Path, entries: tuple[str, ...]) -> None:
    """Batched form of `_ensure_gitignore_entry` (P3 of PLAN-p6-p7-worktree-
    finalize): ONE `git check-ignore --stdin` for all entries instead of one
    subprocess per entry. Same semantics — skip exact-line matches, skip
    entries subsumed by a broader existing pattern, append the rest atomically.
    Best-effort: any failure falls through to appending the un-subsumed entries.
    """
    from harness_maker.io_utils import atomic_write

    gitignore = project_root / ".gitignore"
    try:
        existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    except OSError:
        return
    existing_lines = {line.strip() for line in existing.splitlines()}
    candidates = [e for e in entries if e not in existing_lines]
    if not candidates:
        return
    # Single batched subsumption check: `git check-ignore --stdin` reads the
    # candidate paths from stdin and prints the subset already ignored by a
    # broader pattern (e.g. a dir-level `.claude/`). returncode 0 = ≥1 ignored,
    # 1 = none, ≥2 = error. Glob-shaped entries (e.g. `.claude/.hm-loop-*`) are
    # treated as literal paths and simply won't match unless covered — same as
    # the per-entry path did.
    covered: set[str] = set()
    try:
        check = subprocess.run(  # noqa: S603
            ["git", "check-ignore", "--stdin"],
            cwd=str(project_root),
            input="\n".join(candidates) + "\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
        if check.returncode in (0, 1):
            covered = {line.strip() for line in check.stdout.splitlines() if line.strip()}
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass  # best-effort — fall through and append all candidates
    to_append = [c for c in candidates if c not in covered]
    if not to_append:
        return
    try:
        sep = "" if (existing == "" or existing.endswith("\n")) else "\n"
        atomic_write(gitignore, existing + sep + "".join(f"{e}\n" for e in to_append))
    except OSError:
        pass  # best-effort; don't fail loop creation over a gitignore write


def _ensure_harness_gitignore(project_root: Path) -> None:
    """Append every harness-churn pattern to the project's .gitignore.

    PLAN-worktree-base-artifact-pollution ADR-002. Keeps the base repo clean
    of self-generated churn so parallel `worktree create` is not blocked and
    finalize does not spuriously stash. Idempotent and subsumption-safe; the
    check-ignore subsumption test is BATCHED into a single subprocess
    (`_ensure_gitignore_entries`) rather than one per pattern (P3).
    """
    _ensure_gitignore_entries(project_root, _HARNESS_GITIGNORE_PATTERNS)


def _detect_existing_worktree(base: Path) -> Path | None:
    """Idempotent dispatch helper — return the enclosing real git worktree.

    Path-based detection only (ADR-006): walk ``base.parts`` right-to-left
    looking for a ``.worktrees/<name>/`` structure with a ``.git`` entry.

    Marker-based detection was removed because it caused parallel sessions to
    cross-detect each other's worktrees — Session B would find Session A's
    marker and reuse Session A's worktree instead of creating its own.

    The loop→sub-call idempotency relies on the loop CDing into ``<WT>``
    before dispatching sub-commands (execute stage §0 convention). When the
    sub-command runs with ``$(pwd)=<WT>``, path-based detection returns the
    correct existing worktree without consulting the marker.

    Returns the worktree root Path on confirmed match, else None.
    """
    # Path-based: walk right-to-left so nested .worktrees pick innermost.
    parts = base.parts
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] != WORKTREE_DIR_NAME:
            continue
        if i + 1 >= len(parts):
            continue  # at .worktrees itself, no <name> child yet
        candidate = Path(*parts[: i + 2])
        if not candidate.is_dir():
            continue
        # Use canonical `git rev-parse --git-dir` check rather than
        # `.git`-existence (REVIEW round 4 P1: planted regular file at
        # `<dir>/.git` would otherwise pass as a worktree).
        if _is_git_repo(candidate):
            return candidate
    return None


def _session_worktrees(project_root: Path, primary_wt_name: str, fallback: Path) -> list[Path]:
    """Return all WTs for this session from the per-session marker file.

    Falls back to [fallback] when the marker is absent/unreadable (backward
    compat — single-repo sessions that wrote no marker, or pre-Phase 2 code).
    """
    from harness_maker.loop_marker import parse_marker_paths

    marker = _marker_path(project_root, primary_wt_name)
    if not marker.is_file():
        return [fallback]
    try:
        text = marker.read_text(encoding="utf-8")
    except OSError:
        return [fallback]
    # Drop the `claude_session_id:` content header by the "/"-prefix rule (W1);
    # only absolute path lines are session worktrees.
    paths = [Path(p) for p in parse_marker_paths(text)]
    return paths if paths else [fallback]


def _is_task_worktree(wt: Path) -> bool:
    """True when `wt` is checked out on an `hm/<slug>` task branch (new model).

    Distinguishes a persistent task worktree from a legacy disposable
    `execute-<uuid>` worktree so a migration-window flag flip (ADR-008) routes
    each worktree to the correct finalize path: a worktree created by the OLD
    `create` while the flag was off, then finalized after the flag flipped, must
    still take the old stash+merge+clean path — not commit-and-leave (which
    would leak the disposable worktree). Absent-case discipline (validator W4).
    """
    if not wt.is_dir():
        return False
    try:
        return _current_branch(wt).startswith(_TASK_BRANCH_PREFIX)
    except RuntimeError:
        return False


def _worktree_is_dirty(wt: Path) -> bool:
    """True when `git status --porcelain` is non-empty (uncommitted, non-ignored
    changes remain). A status failure returns False — the caller already handles
    capture errors, and a broken status check after a successful capture is not a
    durability signal we can act on."""
    try:
        return bool(_run(["git", "status", "--porcelain"], cwd=wt.resolve()).stdout.strip())
    except RuntimeError:
        return False


def _finalize_commit_not_stash(all_wts: list[Path]) -> int:
    """ADR-007 (Phase 3): commit-not-stash finalize for the feature-branch model.

    Capture each live session worktree's pending work as a WIP commit on its
    checked-out task branch (`hm/<slug>`) — durability is branch-reachable
    commits, NOT a deferred base stash. The base working tree is never touched
    (no `git stash`, no merge-to-base, no `.hm-finalize-stash-*` ref) and the
    persistent worktree is left in place — including on `fail` (a blocked stage
    must not destroy the persistent workspace the next stage reuses; teardown is
    exclusively the Phase-4 land's job, per ADR-006). Leaves zero finalize-stash
    refs by construction, and leaves the loop/session markers untouched (the
    worktrees are still live until land). A worktree dir already gone
    (landed/cleaned by a prior step) is skipped — idempotent re-run.

    Multi-WT (sibling repos) is best-effort: each WT is captured independently
    and a failure on one does NOT skip the others (maximize durability), but the
    overall return code is 1 if ANY capture failed — finalize never reports a
    false success that would let `/hm:execute` advance over un-committed work.
    Phase 3 targets the single-repo task; the loop preserves the existing
    multi-WT iteration for forward-compat.

    Two safety rails (REVIEW iter-3 consensus, data-loss-sensitive core):
    - **Per-WT identity routing (fail-closed)**: a non-`hm/` worktree present in
      a mixed-migration marker is NEVER commit-and-left here — it is surfaced
      (`rc=1`) and preserved, not silently mishandled (code-reviewer P3 + Codex
      P2). In single-repo Phase 3 the primary is already gated as a task WT, so
      this is forward-safety that never fires in the common path.
    - **Post-capture durability re-check**: a concurrent writer can dirty the
      worktree between `_capture_pending_in_worktree`'s status check and its
      commit; if residual dirt remains, `rc=1` (never a false success a later
      land could trust before teardown) (Codex P1).
    """
    overall_rc = 0
    for current_wt in all_wts:
        if not current_wt.is_dir():
            continue
        if not _is_task_worktree(current_wt):
            print(
                f"[finalize] {current_wt.name} is not an hm/ task worktree; "
                "refusing commit-not-stash on it (mixed marker?) — preserving, "
                "resolve manually",
                file=sys.stderr,
            )
            overall_rc = 1
            continue
        try:
            captured = _capture_pending_in_worktree(current_wt)
            if captured:
                print(
                    f"[finalize] committed pending work in {current_wt.name} "
                    "on its task branch (commit-not-stash, ADR-007)",
                    file=sys.stderr,
                )
        except RuntimeError as e:
            print(
                f"failed to capture uncommitted work in {current_wt}: {e}; preserving worktree",
                file=sys.stderr,
            )
            overall_rc = 1
            continue
        if _worktree_is_dirty(current_wt):
            print(
                f"[finalize] {current_wt.name} still dirty after capture "
                "(concurrent writer?) — NOT reporting success; preserving worktree",
                file=sys.stderr,
            )
            overall_rc = 1
    return overall_rc


def _cli_finalize(args: list[str]) -> int:
    """`python -m harness_maker.worktree finalize <wt_path> <success|fail|stage-only> [strategy]`.

    On success: merge back (default strategy: squash) + cleanup with --force.
    On stage-only: merge with --no-commit (changes staged on base branch) +
        cleanup with --force. Used by `/hm:execute` Step 5 when wrapup will
        own the user-facing commit (single-commit-owner pattern).
    On fail: skip merge; cleanup non-force (preserves dirty worktree for inspection).

    Multi-repo (Phase 4, ADR-003/005/006): reads all WTs from the per-session
    marker file and processes them in order. Fail-fast on first error (success
    path only): emits per-repo status to stderr and returns 1; marker is kept
    so the gate continues protecting surviving worktrees. Idempotent re-run:
    WTs whose directory no longer exists (already cleaned) are skipped.
    """
    if len(args) < 2 or len(args) > 3:
        print(
            "usage: finalize <wt_path> <success|fail|stage-only> [strategy]",
            file=sys.stderr,
        )
        return 2
    wt_str, status = args[0], args[1]
    strategy = args[2] if len(args) == 3 else "squash"
    if status not in {"success", "fail", "stage-only"}:
        print("status must be 'success' | 'fail' | 'stage-only'", file=sys.stderr)
        return 2
    if strategy not in {"squash", "merge"}:
        # Why reject: merge() only knows squash/merge; an unknown value (e.g.
        # "rebase") would otherwise build an invalid `git merge --rebase` command.
        print(f"strategy must be 'squash' | 'merge', got {strategy!r}", file=sys.stderr)
        return 2
    wt = Path(wt_str)
    # Project root = parent of `.worktrees/<name>` (mirrors cleanup's logic).
    project_root = wt.resolve().parent.parent
    primary_wt_name = wt.resolve().name
    auto_commit = status == "success"

    all_wts = _session_worktrees(project_root, primary_wt_name, wt)

    # Nothing to do if all WTs have already been cleaned up (idempotent no-op).
    if not any(p.is_dir() for p in all_wts):
        return 0

    # ADR-007 (Phase 3): commit-not-stash finalize. Route to the new path only
    # for a genuine task worktree (checked out on `hm/<slug>`) under the flag —
    # a legacy disposable `execute-<uuid>` worktree finalized during the
    # migration window (flag flipped while it was in flight) still takes the old
    # stash+merge+clean path below (absent-case discipline; validator W4). The
    # new path captures pending work as branch commits and NEVER tears the
    # persistent worktree down, for `fail` too (validator critical: a clean
    # persistent WT must survive a blocked stage; teardown is Phase-4 land).
    if _is_task_worktree(wt):
        if not worktree_enabled(project_root):
            # A persistent `hm/<slug>` worktree exists but the harness now says isolation
            # is OFF. Falling through to the legacy path would squash-merge an unlanded
            # task branch into base HEAD and then `git worktree remove --force` the
            # directory — the count:3 `worktree-finalize-pulls-orphan-wip-into-main`
            # shape, reachable by a hand-edit that bypasses `disable_preflight`. Refuse.
            try:
                slug = _current_branch(wt).removeprefix("hm/")
            except RuntimeError:
                slug = wt.name
            print(
                f"[finalize] refusing: {wt} is a task worktree on `hm/{slug}` but "
                "harness.yaml says worktree.enabled is off.\n"
                f"  Land it first:  hm worktree task-land {slug}\n"
                "  Or re-enable:   harness-maker make . --worktree",
                file=sys.stderr,
            )
            return 1
        return _finalize_commit_not_stash(all_wts)

    if status == "fail":
        # Fail path: best-effort cleanup of all WTs; marker stays (ADR-003/005).
        overall_rc = 0
        for current_wt in all_wts:
            if not current_wt.is_dir():
                continue
            try:
                cleanup(current_wt, on_success=False)
            except RuntimeError as e:
                print(
                    f"cleanup failed, worktree preserved at {current_wt}: {e}",
                    file=sys.stderr,
                )
                overall_rc = 1
        return overall_rc

    # success / stage-only: fail-fast multi-WT merge loop.
    succeeded: list[Path] = []
    # `pending` is a set: `.discard()` is O(1) and doesn't raise if the value
    # was never added (idempotent re-runs may skip an already-cleaned WT).
    pending: set[Path] = set(all_wts)

    for current_wt in all_wts:
        if not current_wt.is_dir():
            # Already processed in a prior run (idempotent re-run).
            succeeded.append(current_wt)
            pending.discard(current_wt)
            continue

        wt_rc = 0
        pop_rc = 0
        base_repo = current_wt.resolve().parent.parent

        # ADR-005: submodule dirty state cannot be transparently isolated.
        # Probe BEFORE stashing so we never leave an orphan stash on abort.
        try:
            _probe_submodules(base_repo)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 1

        # ADR-003: the base stash now runs INSIDE the merge fence (below), not
        # here — two parallel finalizes must not `git stash push` the same base
        # concurrently. handed_off: True means recovery is owned by a downstream
        # actor (the wrapup-side post-commit-pop); when True the finally clause
        # must NOT pop (it would re-contaminate the index with the user's dirty
        # on top of the staged squash — validator 2nd-pass critical). Both are
        # initialized before the outer try so the finally always has a value;
        # the real handed_off is computed AFTER the fence releases (ADR-003
        # pinned lower boundary).
        stash_ref: str | None = None
        handed_off = False
        staged_before: set[str] = set()

        try:
            # CRITICAL: capture uncommitted work before merge — see finalize bug 2026-05-08.
            try:
                captured = _capture_pending_in_worktree(current_wt)
                if captured:
                    print(
                        f"[finalize] captured uncommitted work in {current_wt.name} as WIP commit",
                        file=sys.stderr,
                    )
            except RuntimeError as e:
                print(
                    f"failed to capture uncommitted work in {current_wt}: {e}; preserving worktree",
                    file=sys.stderr,
                )
                wt_rc = 1

            if wt_rc == 0:
                # PLAN-worktree-cross-session-data-loss-defense ADR-005 merge
                # fence (serialize parallel finalize) + PLAN-p6-p7-worktree-
                # finalize ADR-003 boundary widening: the fence wraps EXACTLY
                # the base-mutating critical section — {stash, staged_before
                # snapshot, merge}. ADR-001 stashes base's pre-existing dirty so
                # the squash runs on a clean tree; staged_before MUST be captured
                # STRICTLY AFTER the stash (ADR-006 scope-guard reads the
                # post-stash index, so the --allow-dirty-base path is exempt);
                # then the squash merge. The fence (a context manager) releases
                # on every exit, INCLUDING the stash-failure path below.
                try:
                    with _acquire_merge_fence(base_repo, timeout=_FENCE_TIMEOUT):
                        stash_ref = _stash_base_dirty(base_repo, current_wt.name)
                        staged_before = _snapshot_staged_paths(base_repo)
                        merge(current_wt, strategy=strategy, commit=auto_commit)
                except (RuntimeError, TimeoutError) as e:
                    print(
                        f"[finalize] stash/merge failed, preserving worktree: {e}",
                        file=sys.stderr,
                    )
                    wt_rc = 1

                # ADR-003: compute the real handed_off AFTER the fence releases
                # (still inside this `if wt_rc == 0` block, so it does not orphan
                # the scope-guard below). A clean base (no stash) is vacuously
                # complete — the finally pops nothing. If `_capture` above failed,
                # this block is skipped and handed_off stays False with stash_ref
                # None, so the finally still pops nothing (correct). If the merge
                # raised after a successful stash, handed_off is False here and
                # the finally rolls the stash back.
                handed_off = stash_ref is None

                # ADR-006 scope-guard (warn-only initial; Phase 7 promotes
                # to halt-mode after sandbox gitignore eliminates false
                # positives).
                if wt_rc == 0:
                    try:
                        ok, contamination = _verify_scope_subset(
                            base_repo, current_wt.name, staged_before
                        )
                        if not ok:
                            print(
                                f"[finalize] WARN scope-guard violation "
                                f"(warn-only mode): {sorted(contamination)} "
                                f"— files staged by merge but NOT in worktree "
                                f"diff. PLAN-worktree-cross-session-data-loss-"
                                f"defense ADR-006.",
                                file=sys.stderr,
                            )
                    except RuntimeError as e:
                        print(f"[finalize] scope-guard check failed: {e}", file=sys.stderr)

            # ADR-001 §2 stage-only handshake: write the ref file AFTER merge
            # succeeds but BEFORE cleanup, then flip handed_off. Cleanup failure
            # after this point cannot re-contaminate because the finally pop is
            # suppressed by handed_off=True; recovery is owned by post-commit-pop.
            # ADR-002: pass the PRIMARY repo's marker path so sibling refs point
            # at the primary marker (siblings have no marker of their own).
            if wt_rc == 0 and not auto_commit and stash_ref is not None:
                try:
                    primary_marker = _marker_path(project_root, primary_wt_name)
                    # Only the primary's ref file records the sibling list;
                    # post-commit-pop reads sibling_bases from the FIRST valid
                    # ref under primary's `.claude/` and uses it as the scan
                    # set. Sibling refs leave the field empty (no recursion).
                    siblings_for_ref: list[Path] = (
                        [p.resolve().parent.parent for p in all_wts[1:]]
                        if current_wt == all_wts[0] and len(all_wts) > 1
                        else []
                    )
                    _write_stash_ref_file(
                        base_repo,
                        current_wt.name,
                        stash_ref,
                        primary_marker,
                        sibling_bases=siblings_for_ref,
                    )
                    print(
                        "[finalize] base WIP stashed; deferred restore will run "
                        "during wrapup post-commit-pop",
                        file=sys.stderr,
                    )
                    handed_off = True
                except (OSError, RuntimeError) as e:
                    # OSError = atomic_write disk failure.
                    # RuntimeError = sibling_bases encoding violation
                    # (reserved char in path). Both route through the same
                    # rollback path so finally pops the base stash.
                    print(
                        f"[finalize] ref file write failed: {e}; rolling back",
                        file=sys.stderr,
                    )
                    wt_rc = 1

            if wt_rc == 0:
                # PLAN-worktree-deliverable-blocks-create ADR-003: record the
                # landed marker (branch tip, post-`_capture_pending_in_worktree`)
                # BEFORE cleanup, on BOTH clean- and dirty-base paths — the
                # `handed_off` handshake block above is stash-conditional and
                # would miss the common clean-base finalize. Writing pre-cleanup
                # means a cleanup failure (worktree dir preserved) can't leave a
                # markerless branch. Best-effort: the marker is a sweep
                # optimization, not a correctness gate.
                try:
                    _write_landed_marker(base_repo, current_wt.name)
                except RuntimeError as e:
                    print(
                        f"[finalize] landed-marker skipped for {current_wt.name}: {e}",
                        file=sys.stderr,
                    )
                try:
                    cleanup(current_wt, on_success=True)
                except RuntimeError as e:
                    print(
                        f"cleanup failed, worktree preserved at {current_wt}: {e}",
                        file=sys.stderr,
                    )
                    wt_rc = 1

            # Success mode pop happens INSIDE the envelope: in success mode the
            # squash is already in HEAD (commit=True), so popping over the now-
            # clean index is safe even if cleanup failed.
            if wt_rc == 0 and auto_commit and stash_ref is not None:
                ok, klass, files = _fenced_restore_base_dirty(base_repo, stash_ref)
                handed_off = True  # success-mode pop done; suppress finally pop
                if not ok:
                    _emit_pop_failure_signal(klass, stash_ref, files, current_wt.name)
                    pop_rc = 1
        finally:
            # Rollback path: only pop when something raised BEFORE handoff.
            # Reset the partial/conflicted merge to HEAD first so the pop doesn't
            # apply over half-applied merge state. CR1 fix (PLAN-p6-p7-worktree-
            # finalize REVIEW): gate on `wt_rc != 0` (ANY failure rollback), not
            # `not auto_commit` — a success-mode `git merge --squash` CONFLICT
            # also leaves a dirty/conflicted index without committing, and the
            # old stage-only-only guard skipped the reset there, popping over
            # conflict markers. `git reset --hard HEAD` is a no-op when clean.
            if stash_ref is not None and not handed_off:
                if wt_rc != 0:
                    with contextlib.suppress(RuntimeError):
                        _run(["git", "reset", "--hard", "HEAD"], cwd=base_repo)
                ok, klass, files = _fenced_restore_base_dirty(base_repo, stash_ref)
                if not ok:
                    _emit_pop_failure_signal(klass, stash_ref, files, current_wt.name)
                    pop_rc = 1

        if wt_rc == 0 and pop_rc != 0:
            wt_rc = pop_rc

        if wt_rc != 0:
            # Fail-fast: emit per-repo status; keep marker so gate protects all.
            remaining = [p for p in pending if p != current_wt]
            print(f"[finalize] succeeded: {[str(s) for s in succeeded]}", file=sys.stderr)
            print(f"[finalize] failed: [{str(current_wt)}]", file=sys.stderr)
            print(f"[finalize] pending: {[str(p) for p in remaining]}", file=sys.stderr)
            print(
                "[finalize] marker kept — re-run 'worktree finalize <WT> ...' after resolving",
                file=sys.stderr,
            )
            return 1

        succeeded.append(current_wt)
        pending.discard(current_wt)

    # All WTs processed successfully. Stage-only handoffs keep the loop marker
    # alive as the session signal post-commit-pop checks before popping; success
    # mode clears immediately because recovery already happened inside finalize.
    if status == "success" or not any(
        _stash_ref_path(p.resolve().parent.parent, p.name).is_file() for p in all_wts
    ):
        _clear_loop_marker(project_root, primary_wt_name)
    return 0


def _cli_post_commit_pop(args: list[str]) -> int:
    """Wrapup handshake: pop deferred stashes (ADR-001 §2, post-commit-pop CLI).

    Globs ``<base_dir>/.claude/.hm-finalize-stash-*`` ref files for the primary
    base AND every sibling base read from ``<primary>/.claude/harness.yaml``
    ``sibling_repos`` (multi-repo M-P0-1 closure). For each ref, validates the
    body via ``_validate_stash_ref_fields``, checks the recorded session_marker
    is still live, and pops the stash IN THE REPO THE REF RECORDS (M-P0-2 fix:
    use ``fields['base']`` for the pop target, not the primary base passed in
    via argv — sibling stashes live in sibling git repos).

    Exit codes:
      0 — every actionable ref popped cleanly (or no refs found, or all stale).
      1 — at least one pop failed; the failing ref + stash are preserved with
          a classified signal so the wrapup-side LLM can AskUserQuestion.
    """
    if len(args) != 1:
        print("usage: post-commit-pop <primary_base>", file=sys.stderr)
        return 2
    primary_base = Path(args[0]).resolve()

    # Multi-repo discovery: read sibling_bases from the PRIMARY's ref file body.
    # REVIEW round 3 hardening: each candidate ref file must pass the full
    # _validate_stash_ref_fields schema check AND its session_marker must be
    # currently live. A stale ref from an aborted prior session must NEVER
    # poison the discovery for the current session.
    sibling_bases: list[Path] = []
    primary_claude = primary_base / _LOOP_MARKER_DIR
    if primary_claude.is_dir():
        for ref_file in sorted(primary_claude.glob(f"{_STASH_REF_PREFIX}*")):
            raw = _read_stash_ref_file(ref_file)
            fields = _validate_stash_ref_fields(raw)
            if fields is None:
                continue  # schema fail → not trusted for discovery
            if not _session_marker_present(fields["session_marker"]):
                continue  # stale (dead session) → don't trust its sibling list
            siblings_field = fields.get("sibling_bases", "")
            if siblings_field:
                sibling_bases = [
                    Path(p.strip()).resolve() for p in siblings_field.split("|") if p.strip()
                ]
                # Containment: each MUST be a real git working tree per
                # `git rev-parse --git-dir`. `.git/.exists()` accepted a
                # planted regular file as proof — REVIEW round 3 P1. The
                # canonical git check eliminates that injection.
                sibling_bases = [b for b in sibling_bases if _is_git_repo(b)]
                break  # First live + valid ref's list is authoritative

    # Dedupe while preserving order: sibling pointing back at primary would
    # otherwise scan primary's `.claude/` twice (REVIEW round 2 P2).
    bases_to_scan = list(dict.fromkeys([primary_base, *sibling_bases]))
    bases_set = set(bases_to_scan)  # for O(1) target_base membership checks

    overall_rc = 0
    # Snapshot the glob ONCE per base. Ref files created mid-iteration (e.g.,
    # a sibling session's finalize completes while we're popping) are
    # intentionally deferred to the next post-commit-pop invocation — REVIEW
    # M-P1-5. Defer marker deletions until after the loop so a marker shared
    # across multiple ref files in this invocation cannot be unlinked mid-loop
    # and cause subsequent refs to misclassify as stale — REVIEW P2-2.
    markers_to_unlink: set[Path] = set()

    for base in bases_to_scan:
        claude_dir = base / _LOOP_MARKER_DIR
        if not claude_dir.is_dir():
            continue
        for ref_file in sorted(claude_dir.glob(f"{_STASH_REF_PREFIX}*")):
            raw_fields = _read_stash_ref_file(ref_file)
            # ADR-002: validate before touching the filesystem. Any invalid
            # field (bad SHA, non-absolute base, path-traversal, symlinked
            # marker) => skip without deleting the ref.
            fields = _validate_stash_ref_fields(raw_fields)
            if fields is None:
                print(
                    f"[post-commit-pop] skipping invalid ref file (validation failed): "
                    f"{ref_file.name}",
                    file=sys.stderr,
                )
                continue

            ref_sha = fields["ref_sha"]
            session_marker = fields["session_marker"]
            # M-P0-2 fix: use the ref-file's own `base` as the pop target —
            # for a sibling's ref file, this is the sibling's repo, not the
            # primary. The argv-derived base is only used for DISCOVERY (the
            # glob entry point); the pop targets the OWNING repo.
            target_base = Path(fields["base"]).resolve()
            # REVIEW round 2 P1 hardening: reject ref files whose `base` field
            # points outside our known scan set. Even though the regex + symlink
            # checks already constrain the field, an adversarial ref pointing
            # at e.g. `/etc` would pass those checks. Containment to the same
            # bases_to_scan we derived from harness.yaml ensures pop targets
            # are real harness-known repos.
            if target_base not in bases_set:
                print(
                    f"[post-commit-pop] ref {ref_file.name} `base` "
                    f"{target_base!r} not in scan set; skipping (path-traversal guard)",
                    file=sys.stderr,
                )
                continue

            # PLAN-worktree-cross-session-data-loss-defense ADR-004: enforce
            # UUID ownership in addition to (existing) session marker
            # existence. Cross-session refs (different UUID) → SKIP. Legacy
            # refs (no session_uuid field) → one-shot accept under sentinel,
            # then permanently reject (migration window of exactly one
            # wrapup invocation per repo per upgrade).
            ref_session_uuid = fields.get("session_uuid", "")
            # PLAN-worktree-cross-session-data-loss-defense Layer 3 status:
            # dirname embed shipped (refs now have distinct per-wt UUIDs)
            # but the OWNED-UUID set inference at this layer is unreliable
            # — `_owned_session_uuids` reads `.hm-loop-*` markers which are
            # shared filesystem state across all sessions (same flaw as
            # the original `_session_marker_present` check). Real fix:
            # wrapup template explicitly passes owned UUIDs to this CLI
            # (via `--owned-uuid <hex>` arg or `HM_SESSION_UUID` env var).
            # That wiring is a separate follow-up; for now the marker-exists
            # fallback below preserves prior (vulnerable) behavior but the
            # dirname embed ensures the EVENTUAL fix has the right data.
            #
            # When `--owned-uuid` IS passed by caller, enforce strict match.
            owned_uuids_arg = os.environ.get("HM_OWNED_SESSION_UUIDS", "").split(",")
            owned_uuids = {u.strip() for u in owned_uuids_arg if u.strip()}
            if ref_session_uuid and ref_session_uuid not in owned_uuids:
                owned_preview = ",".join(sorted(u[:8] for u in owned_uuids))
                print(
                    f"[post-commit-pop] cross-session ref ({ref_session_uuid[:8]} "
                    f"not in HM_OWNED_SESSION_UUIDS {{{owned_preview}}}): "
                    f"{ref_file.name} — skipping (Layer 3 strict mode)",
                    file=sys.stderr,
                )
                continue
            # Legacy ref (empty session_uuid OR sentinel) passes through to
            # the existing _session_marker_present check below — that's the
            # one-shot migration: we accept this once and let downstream
            # finalize re-write with a real UUID.

            if not _session_marker_present(session_marker):
                print(
                    f"[post-commit-pop] stale ref (session marker {session_marker!r} "
                    f"not active): {ref_file.name} — skipping, stash + ref preserved",
                    file=sys.stderr,
                )
                continue

            # Live session match — pop and clean up.
            wt_name = ref_file.name[len(_STASH_REF_PREFIX) :]
            ok, klass, files = _restore_base_dirty(target_base, ref_sha)
            if not ok:
                _emit_pop_failure_signal(klass, ref_sha, files, wt_name)
                overall_rc = 1
                continue

            # Successful pop: delete the ref file inline (each ref is owned by
            # exactly one iteration). The session marker is deferred to a
            # post-loop set so a marker referenced by multiple refs in the
            # same invocation is not deleted mid-loop.
            ref_file.unlink(missing_ok=True)
            markers_to_unlink.add(Path(session_marker))

    # Post-loop: clean up markers belonging to successfully popped sessions.
    for marker in markers_to_unlink:
        marker.unlink(missing_ok=True)

    return overall_rc


def _cli_owned_uuids(args: list[str]) -> int:
    """`python -m harness_maker.worktree owned-uuids <base_dir>` — CSV of active UUIDs.

    PLAN-worktree-cross-session-data-loss-defense task #14: wrapup template
    captures the active-marker owned set via this subcommand and exports it
    as `HM_OWNED_SESSION_UUIDS` env before invoking `post-commit-pop`, which
    then runs in Layer 3 strict mode (cross-session refs SKIPped).

    Prints the CSV (or empty string) to stdout, newline-terminated. Empty
    output is a legitimate "no active sessions" state, not an error.

    DEPRECATED (PLAN-layer3-per-session-ownership ADR-004): this returns ALL
    sessions' marker UUIDs (shared FS state), NOT a per-session owned set. Feeding
    it to `post-commit-pop` makes a session restore a PEER's deferred stash. Use
    the slug crumb (`owned-crumb-read`) / `wt-uuid` instead. Kept for back-compat;
    no template sources from it.
    """
    if len(args) != 1:
        print("usage: owned-uuids <base_dir>", file=sys.stderr)
        return 2
    print(
        "[owned-uuids] DEPRECATED diagnostic-only — returns ALL sessions' UUIDs, "
        "NOT a per-session owned set; do NOT pipe to post-commit-pop "
        "(PLAN-layer3-per-session-ownership ADR-004). Use owned-crumb-read / wt-uuid.",
        file=sys.stderr,
    )
    base = Path(args[0]).resolve()
    uuids = sorted(_owned_session_uuids(base))
    print(",".join(uuids))
    return 0


def _cli_wt_uuid(args: list[str]) -> int:
    """`wt-uuid <wt-path-or-name>...` — CSV of per-session uuids parsed from each
    `execute-<uuid>-<ts>` basename (pure string parse; the path need not exist).

    PLAN-layer3-per-session-ownership ADR-001. Empty stdout for an unparseable
    (e.g. slug) name is the fail-safe signal; a stderr warning aids the operator.
    """
    if not args:
        print("usage: wt-uuid <wt-path-or-name>...", file=sys.stderr)
        return 2
    uuids: list[str] = []
    for arg in args:
        u = _extract_uuid_from_wt_name(Path(arg).name)
        if u:
            uuids.append(u)
        else:
            print(
                f"[wt-uuid] no uuid in {Path(arg).name!r} "
                "(not an execute-<uuid>-<ts> worktree) — empty",
                file=sys.stderr,
            )
    print(",".join(uuids))
    return 0


def _cli_owned_crumb_add(args: list[str]) -> int:
    """`owned-crumb-add <base_dir> <slug> <uuid>` — record an owned uuid (ADR-001)."""
    if len(args) != 3:
        print("usage: owned-crumb-add <base_dir> <slug> <uuid>", file=sys.stderr)
        return 2
    if not args[1].strip():
        # REVIEW P2: an empty slug (LLM missed the <slug> substitution) would write
        # a shared `.hm-owned-uuids-` crumb across unrelated tasks → cross-task pop.
        print("owned-crumb-add: <slug> must be non-empty", file=sys.stderr)
        return 2
    _owned_crumb_add(Path(args[0]).resolve(), args[1], args[2])
    return 0


def _cli_owned_crumb_read(args: list[str]) -> int:
    """`owned-crumb-read <base_dir> <slug>` — CSV of this slug's owned uuids."""
    if len(args) != 2:
        print("usage: owned-crumb-read <base_dir> <slug>", file=sys.stderr)
        return 2
    if not args[1].strip():
        # REVIEW P2: empty slug → empty CSV (fail-safe), not a shared-crumb read.
        print("owned-crumb-read: <slug> must be non-empty", file=sys.stderr)
        return 2
    print(",".join(_owned_crumb_read(Path(args[0]).resolve(), args[1])))
    return 0


def _cli_owned_crumb_clear(args: list[str]) -> int:
    """`owned-crumb-clear <base_dir> <slug>` — drop the slug crumb after a pop."""
    if len(args) != 2:
        print("usage: owned-crumb-clear <base_dir> <slug>", file=sys.stderr)
        return 2
    if not args[1].strip():
        print("owned-crumb-clear: <slug> must be non-empty", file=sys.stderr)
        return 2
    _owned_crumb_clear(Path(args[0]).resolve(), args[1])
    return 0


def _cli_verify(args: list[str]) -> int:
    """`python -m harness_maker.worktree verify <worktree_path>` — anti-drift gate.

    WHY: defends against LLM ``<WT>``-substitution drift — the driver running on
    a path that ``worktree create`` never printed. The loop/execute driver runs
    this immediately after ``create`` and HALTs on a non-zero exit instead of
    cascade-cancelling a parallel stage batch.

    The gate confirms structural validity, NOT name format: exit 0 (re-prints
    the resolved path) means the path is an existing **linked** git worktree
    root; exit 1 means missing, not a git worktree, a subdirectory of one, or
    the **main** checkout (a drifted path that lands on the repo root must not
    pass — review CR-1). It deliberately does not parse the ``execute-<uuid>-<ts>``
    dirname; a non-existent fabricated path is already caught by ``is_dir()``.
    """
    if len(args) != 1:
        print("usage: verify <worktree_path>", file=sys.stderr)
        return 2
    wt = Path(args[0]).resolve()
    if not wt.is_dir():
        print(f"[verify] FAIL: {wt} is not an existing directory", file=sys.stderr)
        return 1
    try:
        cp = _run(["git", "rev-parse", "--show-toplevel"], cwd=wt)
        git_dir = _run(["git", "rev-parse", "--git-dir"], cwd=wt).stdout.strip()
        common_dir = _run(["git", "rev-parse", "--git-common-dir"], cwd=wt).stdout.strip()
    except RuntimeError as e:
        print(f"[verify] FAIL: {wt} is not inside a git worktree ({e})", file=sys.stderr)
        return 1
    top = Path(cp.stdout.strip()).resolve()
    if top != wt:
        print(
            f"[verify] FAIL: {wt} is not a worktree root (git toplevel={top})",
            file=sys.stderr,
        )
        return 1
    # A linked worktree has a per-worktree git-dir (.git/worktrees/<name>) that
    # differs from the shared common-dir; the main checkout has them equal. The
    # loop only calls verify when `create` produced an isolated worktree, so the
    # main repo root passing here would mean the driver drifted onto main.
    if (wt / git_dir).resolve() == (wt / common_dir).resolve():
        print(
            f"[verify] FAIL: {wt} is the main repo root, not a linked worktree "
            "— `worktree create` output drifted; re-run it",
            file=sys.stderr,
        )
        return 1
    print(str(wt))
    return 0


def _cli_cleanup_all(args: list[str]) -> int:
    """`python -m harness_maker.worktree cleanup-all [base_dir] [--force]`.

    WHY: the autoloop iter/phase-blocker path documented in CLAUDE.md
    ("강제 cleanup → halt 전 모든 .worktrees/* 제거") had no reachable caller —
    ``cleanup_all`` was defined but never wired into the CLI dispatch, so the
    disk-accumulation defense could never fire. The loop/execute blocker path
    invokes this before halting.
    """
    rest = [a for a in args if a != "--force"]
    force = "--force" in args
    base = Path(rest[0]).resolve() if rest else Path.cwd()
    removed = cleanup_all(base, force=force)
    print(removed)
    return 0


def _print_prune_warnings(report: PruneReport) -> None:
    """Print prune warnings, collapsing the preserved-branch wall to ONE line.

    PLAN-worktree-deliverable-blocks-create ADR-004: the routine "content not
    fully present" preserves (the 74-line noise) summarize to a single
    actionable line; genuine failures (e.g. `git branch -D … failed`) still
    print individually.
    """
    routine = [(b, h) for (b, h) in report.preserved_branches if "not fully present" in h]
    routine_hints = {h for _, h in routine}
    if routine:
        print(
            f"[WARN] worktree prune: {len(routine)} branch(es) preserved "
            f"(content not verifiably landed). Run `python -m harness_maker.worktree "
            f"prune-branches` to review, or `… prune-branches --force` to delete "
            f"after a `git log -p <branch>` check.",
            file=sys.stderr,
        )
    for warning in report.warnings:
        if warning in routine_hints:
            continue
        print(f"[WARN] worktree prune: {warning}", file=sys.stderr)


def _cli_prune_branches(args: list[str]) -> int:
    """`python -m harness_maker.worktree prune-branches [base_dir] [--force]`.

    PLAN-worktree-deliverable-blocks-create ADR-004: drain the legacy backlog of
    owned-prefix branches whose worktree dir is gone. The no-flag pass runs the
    same gate as `prune_stale` (marker-matched or content-in-HEAD branches are
    swept; the rest preserve+warn). `--force` deletes the remaining
    markerless/diverged branches but prints a `git log -p <branch>` recovery hint
    per branch first (reflog `wip(execute)` commits survive the gc window).
    `--force` is parsed explicitly (not a substring-`in args` check).
    """
    rest = [a for a in args if a != "--force"]
    force = "--force" in args
    base = Path(rest[0]).resolve() if rest else Path.cwd()

    report = prune_stale(base)
    for b in report.removed_branches:
        print(f"deleted branch (landed): {b}")
    for marker_branch in report.removed_landed_markers:
        print(f"reaped orphan landed marker: {marker_branch}")

    if not force:
        for _branch, hint in report.preserved_branches:
            print(f"preserved: {hint}")
        if report.preserved_branches:
            print(
                f"\n{len(report.preserved_branches)} branch(es) preserved. Re-run "
                f"with --force to delete (inspect first with the printed "
                f"`git log -p` hints)."
            )
        return 0

    # --force: delete the branches prune_stale preserved (markerless/diverged),
    # surfacing the recovery hint before each destructive `git branch -D`.
    registered = _registered_worktree_paths(base)
    deleted = 0
    for branch in _list_owned_branches(base):
        wt_dir = (base / WORKTREE_DIR_NAME / branch).resolve()
        if wt_dir in registered or wt_dir.exists():
            continue  # live worktree — never sweep its branch
        print(f"[recovery] inspect before relying on gc: git log -p {branch}")
        try:
            _run(["git", "branch", "-D", branch], cwd=base)
        except RuntimeError as exc:
            print(f"failed to delete {branch}: {exc}", file=sys.stderr)
            continue
        _delete_landed_marker(base, branch)
        deleted += 1
        print(f"deleted branch (--force): {branch}")
    print(f"\n{deleted} branch(es) deleted with --force.")
    return 0


# ── Phase 1 (ADR-008): feature-branch-workflow flag ──────────────────────────

_SESSIONS_FILE = ".claude/.hm-sessions.json"
_FLAG_WARNED = False


def _reset_flag_warning_state() -> None:
    """Test hook: clear the once-per-process absent-flag warning guard."""
    global _FLAG_WARNED
    _FLAG_WARNED = False


class WorktreeResolution(NamedTuple):
    """Outcome of the three-generation `worktree:` block resolution.

    ``value is None`` means *nothing was present* (rung 4) — the caller picks the
    default. Any other rung yields a real bool, so a present-but-malformed key
    resolves fail-closed rather than falling through to a stale lower rung.
    """

    value: bool | None
    rung: int
    diagnostic: str | None


def resolve_worktree_enabled(block: object, *, stage: str | None = "execute") -> WorktreeResolution:
    """Resolve a parsed ``worktree:`` block to the isolation boolean.

    PLAN-worktree-side-defaults ADR-007. First key present wins, newest generation
    first. Two rules exist because their absence was a shipped hazard:

    1. A present-but-non-boolean value **terminates** the lookup fail-closed. Under
       fall-through, ``enabled: "false"`` next to a stale ``feature_branch_workflow:
       true`` would silently turn isolation *on* against the apparent opt-out.
    2. A present ``scope`` terminates too. Falling through on ``scope: []`` would
       contradict first-key-present-wins — and ``scope: []`` is precisely the
       hand-edit a user makes when trying to disable.

    ``stage=None`` means "is isolation on for ANY stage" — the question a *guard* asks.
    It matters only at rung 3: a legacy `scope: ["plan"]` harness has live isolation, but
    resolving it against the default `"execute"` returns False, which would let the
    disable guard conclude there is nothing to strand.

    Callers that only need a bool should use :func:`worktree_enabled`.
    """
    if block is None:
        return WorktreeResolution(None, 0, None)
    if not isinstance(block, dict):
        # A PRESENT but malformed block (`worktree: false`, `worktree: "off"`) is a
        # visible opt-out, not an absence. Treating it as absent let a non-interactive
        # Production re-render run the enablement probe and write `enabled: true` over
        # it — the same fail-closed rule the per-key branches below implement.
        # rung 1, NOT 0: rung 0 means "nothing present", which is the migration's signal
        # to run that probe.
        return WorktreeResolution(
            False,
            1,
            f"worktree is {block!r}, not a mapping — treating isolation as OFF. Fix harness.yaml.",
        )

    for rung, key in ((1, "enabled"), (2, "feature_branch_workflow")):
        if key not in block:
            continue
        val = block[key]
        if not isinstance(val, bool):
            return WorktreeResolution(
                False,
                rung,
                f"worktree.{key} is {val!r}, not a boolean — refusing to guess. "
                "Fix harness.yaml (isolation is treated as OFF until you do).",
            )
        if rung == 1:
            legacy = _legacy_disagreement(block, val, stage=stage)
            return WorktreeResolution(val, 1, legacy)
        return WorktreeResolution(val, 2, None)

    if "scope" in block:
        scope = block["scope"]
        if not isinstance(scope, list):
            return WorktreeResolution(
                False,
                3,
                f"worktree.scope is {scope!r}, not a list — treating isolation as OFF.",
            )
        on = bool(scope) if stage is None else (stage in scope)
        return WorktreeResolution(on, 3, None)

    return WorktreeResolution(None, 0, None)


def _legacy_disagreement(block: dict[str, object], value: bool, *, stage: str | None) -> str | None:
    """Warn when a retired key contradicts `enabled` (ADR-007).

    `enabled` still wins — it is the newest explicit decision — but a silent flip
    is exactly the name-reuse hazard the second opinion flagged, so make it visible.
    """
    legacy = block.get("feature_branch_workflow")
    if isinstance(legacy, bool) and legacy != value:
        return (
            f"worktree.enabled is {value} but the retired "
            f"worktree.feature_branch_workflow says {legacy}; using enabled. "
            "Delete the retired key."
        )
    scope = block.get("scope")
    if not isinstance(scope, list):
        return None
    _scope_on = bool(scope) if stage is None else (stage in scope)
    if _scope_on != value:
        return (
            f"worktree.enabled is {value} but the retired worktree.scope "
            f"({scope!r}) implies {not value}; using enabled. Delete the retired key."
        )
    return None


def worktree_enabled(base_dir: Path, *, stage: str = "execute") -> bool:
    """Read harness.yaml and resolve the worktree-isolation boolean.

    THE single runtime reader (PLAN-worktree-side-defaults ADR-001/007). Every
    behavior-bearing consumer routes through this — a second reader that diverges
    means `/hm:health` can report a different mode than the one executing.

    ``stage`` is consulted only by the legacy `scope` rung, so an un-re-rendered
    harness keeps its per-stage behavior; rung 1 and 2 are stage-blind by design.
    """
    global _FLAG_WARNED
    yaml_path = base_dir / _LOOP_MARKER_DIR / "harness.yaml"
    try:
        data = load_harness_yaml(yaml_path)
    except (OSError, yaml.YAMLError):
        return False
    res = resolve_worktree_enabled(data.get("worktree"), stage=stage)
    if res.diagnostic:
        print(f"[worktree] {res.diagnostic}", file=sys.stderr)
    if res.value is None:
        if not _FLAG_WARNED:
            print(
                "[worktree] harness.yaml has no worktree.enabled key → defaulting to "
                "isolation OFF. Re-render with `/harness-maker:make` to set it.",
                file=sys.stderr,
            )
            _FLAG_WARNED = True
        return False
    return res.value


def _feature_branch_workflow_enabled(base_dir: Path) -> bool:
    """Deprecated alias for :func:`worktree_enabled` (PLAN-worktree-side-defaults).

    Retained for one release so an out-of-tree caller does not break; do NOT add
    new call sites — the structural test in
    ``tests/unit/test_worktree_reader_singleton.py`` enforces that.
    """
    return worktree_enabled(base_dir)


# ── Phase 1 (ADR-004): session registry .claude/.hm-sessions.json ─────────────

_REGISTRY_FIELD_RE = re.compile(r"^[^\x00\n\r|]*$")  # no NUL / newline / pipe


@dataclass
class SessionRow:
    """One active /hm: session.

    `session_uuid` is the DESIGNED primary identity (ADR-004). **CLI-boundary reality
    (REVIEW-2026-06-21 P3-1):** the shipped `task-create` / `task-preflight` / `task-land`
    entry points each run in a short-lived subprocess and mint a throwaway
    `uuid.uuid4()` (no stable per-session UUID is threaded — `_current_session_uuid`
    is project-scoped, NOT session-scoped, per REVIEW round 1 P0-MANUAL2, and the real
    per-session identity is the deferred dirname-embedded-UUID refactor). So in the
    shipped path the LIVE-row protection is actually enforced by the `pid`-liveness +
    worktree-existence heuristic in `_drop_own_row` / `reclaim_stale`, NOT by uuid match.
    That heuristic is safe (it only ever drops a same-branch row whose worktree is
    already gone, and preserves a live foreign-pid row — see
    `test_task_land_no_uuid_preserves_foreign_live_pid_row`); the uuid-match path fires
    only when a caller explicitly passes a stable uuid. `pid` is a liveness HINT only."""

    task: str
    branch: str
    worktree: str
    session_uuid: str
    pid: int
    created_at: str


def _valid_registry_fields(row: SessionRow) -> bool:
    """Reject NUL/newline/pipe + path-traversal in user-facing string fields."""
    for value in (row.task, row.branch, row.worktree, row.session_uuid):
        if not isinstance(value, str) or _REGISTRY_FIELD_RE.match(value) is None:
            return False
        if ".." in value.replace("\\", "/").split("/"):
            return False
    return isinstance(row.pid, int) and row.pid > 0


def _read_sessions(base_dir: Path) -> list[SessionRow]:
    """Load the registry. Missing/corrupt/invalid → [] (tolerant, never raises)."""
    path = base_dir / _SESSIONS_FILE
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    rows: list[SessionRow] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            row = SessionRow(
                task=str(item["task"]),
                branch=str(item["branch"]),
                worktree=str(item["worktree"]),
                session_uuid=str(item["session_uuid"]),
                pid=int(item["pid"]),
                created_at=str(item.get("created_at", "")),
            )
        except (KeyError, ValueError, TypeError):
            continue
        if _valid_registry_fields(row):
            rows.append(row)
    return rows


def _write_sessions(base_dir: Path, rows: list[SessionRow]) -> None:
    path = base_dir / _SESSIONS_FILE
    payload = [
        {
            "task": r.task,
            "branch": r.branch,
            "worktree": r.worktree,
            "session_uuid": r.session_uuid,
            "pid": r.pid,
            "created_at": r.created_at,
        }
        for r in rows
        if _valid_registry_fields(r)
    ]
    atomic_write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


_REGISTRY_LOCK = "index.lock-hm-registry"
_REGISTRY_LOCK_TIMEOUT = 30.0


def _registry_mutate(
    base_dir: Path,
    fn: Callable[[list[SessionRow]], list[SessionRow]],
    *,
    strict: bool = False,
) -> None:
    """Lock-serialized read-modify-write of the registry (no lost updates).

    Uses a DEDICATED lock (`index.lock-hm-registry`), NOT the finalize merge
    fence — so a registry mutate never contends with the 360s finalize hold and
    never self-deadlocks if a future call-site runs inside the merge fence
    (REVIEW Phase 1 P1). The registry is operational churn: if the lock cannot
    be acquired (contention OR a stale O_EXCL lock left by a SIGKILL'd process on
    WSL2/NTFS), a permanent wedge is worse than a rare lost update — so fall back
    to a best-effort unfenced mutate + warn, mirroring the finalize-pop fallback.

    `strict=True` DISABLES that fallback (REVIEW k-of-3 P1): an atomic CLAIM cannot
    safely degrade to an unfenced read-modify-write — two concurrent claims would
    both read no foreign row, both write, and silently SHARE the same task worktree.
    A strict mutate re-raises the lock failure so the caller can fail closed.
    """
    try:
        with _acquire_merge_fence(
            base_dir, timeout=_REGISTRY_LOCK_TIMEOUT, lock_basename=_REGISTRY_LOCK
        ):
            rows = _read_sessions(base_dir)
            _write_sessions(base_dir, fn(rows))
        return
    except (TimeoutError, RuntimeError, OSError) as exc:
        if strict:
            raise  # claim: fail closed rather than silently share under a wedge
        print(
            f"[worktree] session-registry lock unavailable ({exc}); best-effort unfenced update",
            file=sys.stderr,
        )
    rows = _read_sessions(base_dir)
    _write_sessions(base_dir, fn(rows))


def _pid_alive(pid: int) -> bool:
    """True if a process with pid exists (liveness HINT only — pid can be reused).

    Relies on the upstream `_valid_registry_fields` `pid > 0` guard: `os.kill(0, 0)`
    signals the caller's process group (returns True), so this helper is unsafe for
    `pid <= 0` and must only be called on validated rows.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    except OSError:
        return False
    return True


class SharedSlugError(Exception):
    """A foreign LIVE session already holds this task branch (ADR-001).

    Deliberately NOT a RuntimeError/OSError subclass — `_registry_mutate`'s fenced
    path catches those and would swallow this onto the unfenced fallback (with a
    misleading "lock unavailable" warning + redundant re-run). A plain Exception
    propagates straight out of the fenced `with`, so the atomic claim never
    half-commits.
    """


def _foreign_live_rows(
    rows: list[SessionRow], *, branch: str, session_uuid: str
) -> list[SessionRow]:
    """Rows representing a DIFFERENT live session holding `branch` (ADR-001).

    'Live' mirrors `reclaim_stale`: pid alive AND worktree dir on disk. A
    truly-simultaneous pre-create window (neither session's dir exists yet) is
    covered by `git worktree add`'s own atomicity — the loser errors loudly and
    rolls back its claim — not by this registry check.
    """
    return [
        r
        for r in rows
        if r.branch == branch
        and r.session_uuid != session_uuid
        and _pid_alive(r.pid)
        and Path(r.worktree).exists()
    ]


def claim_task_branch(
    base_dir: Path,
    *,
    task: str,
    branch: str,
    wt: str,
    session_uuid: str,
    pid: int,
    allow_shared: bool = False,
) -> None:
    """Atomically claim `branch` for this session, or raise `SharedSlugError` (ADR-001).

    The foreign-live check AND the row insert run in ONE `_registry_mutate`
    critical section — a separate pre-read then register would be check-then-act
    and re-open the silent same-slug share (Codex P1). `allow_shared` permits
    intentional pairing (foreign same-branch rows coexist). Own-uuid re-entry
    never conflicts — it attaches (crash-recovery / idempotent re-run).
    """
    row = SessionRow(
        task=task,
        branch=branch,
        worktree=wt,
        session_uuid=session_uuid,
        pid=pid,
        created_at=_timestamp(),
    )
    if not _valid_registry_fields(row):
        return  # adversarial input dropped, never raises

    def _claim(rows: list[SessionRow]) -> list[SessionRow]:
        if not allow_shared and _foreign_live_rows(rows, branch=branch, session_uuid=session_uuid):
            raise SharedSlugError(
                f"task {task!r} (branch {branch}) is already held by another live "
                f"session; pass --allow-shared-slug to share it intentionally"
            )
        if allow_shared:
            kept = [r for r in rows if r.session_uuid != session_uuid]
        else:
            kept = [r for r in rows if r.session_uuid != session_uuid and r.branch != branch]
        kept.append(row)
        return kept

    # Fail CLOSED on a wedged registry lock when NOT allow_shared (REVIEW k-of-3
    # P1): the unfenced fallback would let two concurrent claims both pass the
    # foreign-live check and silently share hm/<slug>. With allow_shared the share
    # is intentional, so best-effort is fine.
    try:
        _registry_mutate(base_dir, _claim, strict=not allow_shared)
    except SharedSlugError:
        raise
    except (TimeoutError, RuntimeError, OSError) as exc:
        raise SharedSlugError(
            f"cannot safely claim task {task!r} (branch {branch}): registry lock "
            f"unavailable ({exc}); retry, or pass --allow-shared-slug to share it"
        ) from exc


def register_session(
    base_dir: Path,
    *,
    task: str,
    branch: str,
    wt: str,
    session_uuid: str,
    pid: int,
) -> None:
    """Claim a task↔branch↔worktree↔session row (ADR-004). Idempotent by uuid."""
    row = SessionRow(
        task=task,
        branch=branch,
        worktree=wt,
        session_uuid=session_uuid,
        pid=pid,
        created_at=_timestamp(),
    )
    if not _valid_registry_fields(row):
        return  # adversarial input dropped, never raises

    def _add(rows: list[SessionRow]) -> list[SessionRow]:
        # Dedup by uuid AND branch → one row per task branch (REVIEW Phase 2 P1:
        # reuse re-registers with a fresh uuid; the prior same-branch row is replaced).
        kept = [r for r in rows if r.session_uuid != session_uuid and r.branch != branch]
        kept.append(row)
        return kept

    _registry_mutate(base_dir, _add)


def release_session(base_dir: Path, *, session_uuid: str) -> None:
    """Remove the row owned by session_uuid (and only that one)."""
    _registry_mutate(base_dir, lambda rows: [r for r in rows if r.session_uuid != session_uuid])


def reclaim_stale(base_dir: Path) -> None:
    """Drop genuinely-dead rows. session_uuid primary; pid is a liveness hint only.

    A row is reclaimed (dropped) iff its worktree dir is missing OR its pid is
    dead — i.e. kept only while BOTH its worktree is on disk AND its pid is live.
    pid-reuse can only make a dead session's pid look alive, which (combined with
    a still-present worktree) merely preserves a stale row — the safe direction.
    Dropping a row only releases the registry claim; it never deletes the worktree.
    """

    def _sweep(rows: list[SessionRow]) -> list[SessionRow]:
        return [r for r in rows if Path(r.worktree).exists() and _pid_alive(r.pid)]

    _registry_mutate(base_dir, _sweep)


# ── Phase 2 (ADR-010): path-ownership classifier ─────────────────────────────


def _path_owner(relpath: str) -> str:
    """Classify a repo path per the ADR-010 path-ownership matrix.

    deliverable → branch-owned, lands in the squash (PLAN/RESEARCH/SPEC/REVIEW,
    human memory tiers). operational → gitignored churn, excluded from squash
    (`.hm-loop-active`, registry, observability, iter-receipts). user → source +
    `.claude/agents|skills|harness.yaml`, preserved. external → outside the repo
    (the second-brain vault), unaffected.
    """
    norm = relpath.replace("\\", "/")
    if norm.startswith("/") or ".." in norm.split("/"):
        return "external"
    if (
        norm == ".hm-loop-active"
        or norm.startswith(".claude/observability/")
        or norm.startswith(".claude/.hm-")
        or norm.startswith(".claude/memory/semantic/")
        or norm.startswith(".claude/memory/episodic/")
        or norm.startswith(".claude/memory/profile/")
    ):
        return "operational"
    if (
        _is_deliverable_path(norm)
        or norm in (".claude/memory/wiki.md", ".claude/memory/failures.md")
        or norm.startswith(".claude/memory/session/")
        # PLAN-harness-diet ADR-015: the failures archive is the same tier as the file it
        # is evicted from, so it must land in the squash rather than read as user dirt.
        # Anchored DIRECTORY prefix, never a substring — this classifier's narrowness is a
        # documented safety invariant.
        or norm.startswith(".claude/memory/archive/")
    ):
        return "deliverable"
    return "user"


# ── Phase 2 (ADR-002, ADR-006): persistent per-task worktree ─────────────────


def task_branch(slug: str) -> str:
    """The user-facing per-task branch name (ADR-002)."""
    return f"{_TASK_BRANCH_PREFIX}{slug}"


def task_worktree_path(base: Path, slug: str) -> Path:
    """The persistent per-task worktree dir (ADR-006)."""
    return base / WORKTREE_DIR_NAME / slug


_TASK_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _valid_task_slug(slug: str) -> bool:
    """Reject slugs that escape `.worktrees/` or inject a git ref (REVIEW Phase 2 P1).

    `_run` is list-argv (no shell), so this guards the FILESYSTEM-path + git-ref
    namespace, not shell injection: no `/`, `\\`, leading `-`/`.`, whitespace,
    absolute path, or `..` component.
    """
    return bool(_TASK_SLUG_RE.match(slug)) and ".." not in slug


def _gitignore_literal(rel: str) -> str:
    """Render `rel` as a LITERAL, anchored gitignore pattern (REVIEW Phase 2 P1).

    A raw filename with gitignore metachars (`#` comment, `!` negation, `*?[]`
    globs, leading/trailing space) would silently fail to exclude → the secret
    lands in the squash. Anchor with `/` and backslash-escape the specials.
    """
    return "/" + re.sub(r"([#!*?\[\]\\ ])", r"\\\1", rel)


def _copy_and_exclude_secrets(base: Path, wt: Path, include: list[str]) -> None:
    """Copy gitignored secrets into the worktree, excluding them via the COMMON
    `.git/info/exclude` (NOT the tracked `.gitignore`, which would land in the
    squash). The secret is anchored+escaped (REVIEW Phase 2 P1).

    Mechanism note (verified empirically): git does NOT honor the per-worktree
    `.git/worktrees/<id>/info/exclude` for status/add — it reads the COMMON
    git-dir's `info/exclude` (`--git-common-dir`). The pattern is anchored with `/`
    so it excludes the secret at each worktree/base root; secrets are never
    track-worthy anywhere, so repo-wide exclusion is acceptable and `.git/` is
    never committed.

    Each `include` entry is containment-checked (REVIEW Phase 2 P1): a traversal /
    absolute path must not read outside `base` or write outside `wt`.
    """
    import shutil

    common = _run(["git", "rev-parse", "--git-common-dir"], cwd=wt).stdout.strip()
    common_dir = Path(common) if Path(common).is_absolute() else (wt / common).resolve()
    exclude = common_dir / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    existing_lines = set(existing.splitlines())
    base_r = base.resolve()
    wt_r = wt.resolve()
    new_lines: list[str] = []
    for rel in include:
        if _path_owner(rel) == "external":  # absolute / `..`-escaping → skip
            continue
        src = base / rel
        dst = wt / rel
        if (
            not src.is_file()
            or not src.resolve().is_relative_to(base_r)
            or not dst.resolve().is_relative_to(wt_r)
        ):
            continue
        # Only copy paths gitignored in base: info/exclude is a no-op for TRACKED
        # files, so copying one would land its modification in the squash (REVIEW
        # Phase 2 P2). `git check-ignore -q` exits 0 iff the path is ignored.
        try:
            _run(["git", "check-ignore", "-q", "--", rel], cwd=base)
        except RuntimeError:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        entry = _gitignore_literal(rel)
        if entry not in existing_lines:
            new_lines.append(entry)
            existing_lines.add(entry)
    if new_lines:
        sep = "" if (not existing or existing.endswith("\n")) else "\n"
        atomic_write(exclude, existing + sep + "\n".join(new_lines) + "\n")


def task_create(
    base_dir: Path,
    slug: str,
    *,
    session_uuid: str,
    include: list[str] | None = None,
    allow_shared: bool = False,
) -> Path:
    """Create (or idempotently reuse) the persistent per-task worktree (ADR-002/006).

    A DETERMINISTIC `.worktrees/<slug>/` on branch `hm/<slug>` off the base HEAD —
    not the ephemeral `execute-<uuid>`. Registers the session (Phase 1) and copies
    gitignored secrets in (excluded via per-worktree info/exclude). Idempotent: a
    repeated call returns the existing worktree and re-establishes the registry row
    (self-healing the absent-case after `reclaim_stale` — REVIEW Phase 2 P1), with
    no duplicate branch or row. Flag-gating is the CALLER's job (Phase 5).
    """
    if not _valid_task_slug(slug):
        raise ValueError(
            f"invalid task slug {slug!r}: expected [A-Za-z0-9][A-Za-z0-9._-]* with no '..'"
        )
    base = base_dir.resolve()
    wt = task_worktree_path(base, slug)
    branch = task_branch(slug)
    # Atomically claim the branch BEFORE creating the worktree (ADR-001): a
    # foreign LIVE session holding it hard-fails here unless allow_shared. The
    # claim IS the (re-)registration — dedups by branch, self-heals a reclaimed
    # row, and own-uuid re-entry attaches.
    claim_task_branch(
        base,
        task=slug,
        branch=branch,
        wt=str(wt),
        session_uuid=session_uuid,
        pid=os.getpid(),
        allow_shared=allow_shared,
    )
    try:
        if not wt.is_dir():
            (base / WORKTREE_DIR_NAME).mkdir(parents=True, exist_ok=True)
            # Reattach an existing branch (persistent dir removed but branch kept)
            # instead of wedging on `-b ... already exists` (REVIEW Phase 2 P1).
            add = (
                ["git", "worktree", "add", str(wt), branch]
                if _branch_exists(base, branch)
                else ["git", "worktree", "add", "-b", branch, str(wt)]
            )
            _run(add, cwd=base)
            if include:
                try:
                    _copy_and_exclude_secrets(base, wt, include)
                except Exception:
                    with contextlib.suppress(RuntimeError):
                        _run(["git", "worktree", "remove", "--force", str(wt)], cwd=base)
                    raise
    except Exception:
        # A failed `git worktree add` (e.g. the loser of a truly-simultaneous
        # create race) must not strand the claim — roll back our own row only.
        release_session(base, session_uuid=session_uuid)
        raise
    return wt


# ── Phase 5 (ADR-002): warm-branch-drift detection + refresh ─────────────────


def _branch_drift(base: Path, branch: str) -> tuple[int, int]:
    """`(behind, ahead)` commit counts of `branch` vs the base repo's HEAD tip.

    behind = commits in base HEAD not reachable from `branch` (the base advanced
    since the task branched). ahead = commits on `branch` not in base HEAD.
    Base tip is the base repo's HEAD SHA — the same parent tip `task_land` squashes
    onto — NOT a hardcoded `main`, so this is robust on repos whose default branch
    isn't `main` (worktree.py:988-1001 precedent). Any git/parse failure → (0, 0)
    (treat as no-drift; never raises)."""
    try:
        base_head = _run(["git", "rev-parse", "HEAD"], cwd=base).stdout.strip()
        ahead = int(
            _run(["git", "rev-list", "--count", f"{base_head}..{branch}"], cwd=base).stdout.strip()
        )
        behind = int(
            _run(["git", "rev-list", "--count", f"{branch}..{base_head}"], cwd=base).stdout.strip()
        )
    except (RuntimeError, ValueError):
        return (0, 0)
    return (behind, ahead)


def task_preflight(
    base_dir: Path,
    slug: str,
    *,
    session_uuid: str,
    allow_shared: bool = False,
    stage: str | None = None,
    claude_session_id: str | None = None,
) -> tuple[Path, list[str]]:
    """Flag-on stage preflight (ADR-002/004/006): ensure the task worktree + warn.

    Idempotently ensures the persistent `.worktrees/<slug>/` task worktree (Phase 2
    `task_create` — reused if present), reclaims genuinely-dead registry rows
    (Phase 1), and returns `(wt_path, warnings)`. Warnings surface (a) a concurrent
    SAME-task session (a different `session_uuid` already on our branch — the
    highest-risk collision), (b) other LIVE sessions on different tasks, and (c) a
    drift notice pointing at `task-refresh` when the task branch fell behind the
    base tip. Flag-gating is the CALLER's job (the template)."""
    base = base_dir.resolve()
    branch = task_branch(slug)
    reclaim_stale(base)  # drop dead rows before surfacing the active set
    # Snapshot the registry BEFORE task_create: its register_session replaces the
    # same-branch row, which would erase a concurrent SAME-slug session's row and
    # hide the highest-risk collision (two agents in the SAME task worktree) from
    # the surface below (REVIEW Codex P2).
    prior = _read_sessions(base)
    warnings: list[str] = []
    same_task = [r for r in prior if r.branch == branch and r.session_uuid != session_uuid]
    if same_task:
        warnings.append(
            f"[preflight] WARNING: {len(same_task)} other session(s) already hold task "
            f"{slug!r} (branch {branch}); concurrent edits to the same worktree can collide."
        )
    other_tasks = sorted(
        {r.task for r in prior if r.branch != branch and r.session_uuid != session_uuid}
    )
    if other_tasks:
        warnings.append(
            f"[preflight] {len(other_tasks)} other active session(s): {', '.join(other_tasks)}"
        )
    wt = task_create(base, slug, session_uuid=session_uuid, allow_shared=allow_shared)
    behind, _ahead = _branch_drift(base, branch)
    if behind > 0:
        # ADR-002: try to auto-resolve drift before merely warning. Refresh is
        # quiet (diagnostics on stderr) and refuses generically (conflict OR
        # dirty OR wrong-branch) returning rc1 — on any decline, fall through to
        # the warning + the land-block backstop.
        refreshed = task_refresh(base, slug) == 0
        if refreshed:
            warnings.append(f"[preflight] task branch {branch} auto-refreshed onto the base tip.")
        else:
            try:
                base_br = _current_branch(base)
            except RuntimeError:
                base_br = "the base branch"
            warnings.append(
                f"[preflight] task branch {branch} is {behind} commit(s) behind "
                f"{base_br}; auto-refresh declined — run `task-refresh {slug}` to rebase."
            )
    # ADR-008: the span START is a SIDE EFFECT of this call, never a separate prose
    # instruction — a prose line can be skipped silently, whereas a stage that skips
    # preflight does not get its `<WT>` and degrades visibly. Emitted only AFTER the
    # claim succeeds: a hard-failing preflight never ran a stage, and an open span
    # from it would be closed only by next-start / session-end / the 400-turn cap,
    # i.e. it could swallow up to 400 unrelated turns.
    #
    # `stage` is None for an un-re-rendered harness (no `--stage`). That writes an
    # EMPTY stage on purpose: the reader maps it to `(unknown-stage)` and counts it,
    # whereas normalising here would leave the absent-case counter at 0 forever.
    _emit_stage_span(
        base,
        stage=stage,
        git_branch=branch,
        task_slug=slug,
        claude_session_id=claude_session_id,
    )
    return wt, warnings


def _emit_stage_span(
    base: Path,
    *,
    stage: str | None,
    git_branch: str | None = None,
    task_slug: str | None = None,
    claude_session_id: str | None = None,
) -> None:
    """Never let telemetry break a stage: emission failure warns and proceeds.

    `stage=None` writes an EMPTY stage on purpose — see ADR-008: the reader maps it
    to `(unknown-stage)` and counts it, whereas normalising here would leave the
    absent-case counter at 0 forever.
    """
    try:
        from .stage_spans import emit_event

        emit_event(
            "start",
            stage=stage or "",
            cwd=base,
            session_id=claude_session_id or os.environ.get("HM_SESSION_ID") or None,
            git_branch=git_branch,
            task_slug=task_slug,
        )
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[span] emission failed (non-fatal): {exc}", file=sys.stderr)


def task_refresh(base_dir: Path, slug: str) -> int:
    """ADR-002: rebase `hm/<slug>` onto the base repo's current tip, in the worktree.

    The rebase target is the base repo HEAD SHA (the parent tip `task_land` squashes
    onto) — NOT a literal `main` (validator W3; worktree.py:988-1001 learned that
    `main` breaks on non-`main` repos). Commits are preserved: a conflict aborts the
    rebase (`git rebase --abort`), restoring the branch exactly, and returns `rc=1`.
    A dirty worktree is refused up front. Returns 0 on a clean rebase or no-op."""
    if not _valid_task_slug(slug):
        print(f"[refresh] invalid task slug {slug!r}", file=sys.stderr)
        return 1
    base = base_dir.resolve()
    branch = task_branch(slug)
    wt = task_worktree_path(base, slug)
    if not wt.is_dir():
        print(f"[refresh] no task worktree for {slug!r} at {wt}", file=sys.stderr)
        return 1
    if _worktree_is_dirty(wt):
        print(
            f"[refresh] worktree {wt} has uncommitted changes; commit or discard before refresh",
            file=sys.stderr,
        )
        return 1
    # Rebase operates on whatever is checked out in `wt`; refuse unless it is the
    # task branch, so a detached HEAD / manual checkout can't get silently rebased
    # while we report success for `hm/<slug>` (REVIEW code P2).
    try:
        checked_out = _current_branch(wt)
    except RuntimeError as exc:
        print(f"[refresh] cannot read worktree branch: {exc}", file=sys.stderr)
        return 1
    if checked_out != branch:
        print(
            f"[refresh] worktree {wt} is on {checked_out!r}, not {branch!r}; "
            "checkout the task branch before refresh",
            file=sys.stderr,
        )
        return 1
    try:
        base_head = _run(["git", "rev-parse", "HEAD"], cwd=base).stdout.strip()
    except RuntimeError as exc:
        print(f"[refresh] cannot resolve base tip: {exc}", file=sys.stderr)
        return 1
    try:
        _run(["git", "rebase", base_head], cwd=wt)
    except RuntimeError as exc:
        with contextlib.suppress(RuntimeError):
            _run(["git", "rebase", "--abort"], cwd=wt)
        print(
            f"[refresh] rebase conflict; aborted, branch {branch} unchanged: {exc}",
            file=sys.stderr,
        )
        return 1
    # Diagnostics go to STDERR, never stdout (ADR-002 / Codex P2): preflight's
    # auto-refresh runs inside `_cli_task_preflight`, whose stdout contract is
    # exactly the `<WT>` path consumed by stage templates.
    print(f"[refresh] {branch} rebased onto {base_head[:12]}", file=sys.stderr)
    return 0


def _split_z(out: str) -> list[str]:
    """Split a NUL-delimited git `-z` stream into raw path strings (trailing
    empty dropped).

    NUL-delimiting is the ONLY enumeration that survives non-ASCII / control-char
    / whitespace filenames intact: git's default `core.quotepath=true` returns
    such names C-quoted (e.g. `café.md` → the literal `"caf\\303\\251.md"`) in the
    newline-delimited form, and a quoted literal handed back as a pathspec never
    matches the real file (REVIEW-2026-06-21 P1-1: land permanently fails + leaves
    staged contamination). `-z` paths are raw bytes-as-str and pass straight
    through subprocess argv (no shell, no requoting)."""
    return [p for p in out.split("\x00") if p]


def _staged_files(base: Path) -> set[str]:
    """Paths currently staged in base's index (`git diff --cached`, NUL-safe).

    The squash-land treats these as a concurrent session's forgiven base churn
    (`.claude/` + deliverables pass `_has_user_dirty_state`) that must NOT land in
    our squash NOR be clobbered by a conflict-cleanup (REVIEW-2026-06-21 P1-2)."""
    try:
        out = _run(["git", "diff", "--cached", "-z", "--name-only"], cwd=base).stdout
    except RuntimeError:
        return set()
    return set(_split_z(out))


def _untracked_files(base: Path) -> set[str]:
    """Non-ignored untracked files (`git ls-files --others --exclude-standard`).

    Used to scope the squash-conflict cleanup to ONLY merge-introduced untracked
    files — a blanket `git clean` would nuke pre-existing untracked deliverables
    (work-docs/PLAN-*.md) that the base-cleanliness gate deliberately forgives.
    `-z` so a non-ASCII untracked name matches the same-encoded `touched` set
    (REVIEW-2026-06-21 P1-1)."""
    try:
        out = _run(["git", "ls-files", "-z", "--others", "--exclude-standard"], cwd=base).stdout
    except RuntimeError:
        return set()
    return set(_split_z(out))


def _squash_path_set(base: Path, branch: str) -> list[str]:
    """The files the squash will touch — branch's changes vs its merge-base with
    HEAD. Bounds both the conflict-cleanup AND the scoped land commit to the
    squash's OWN path set.

    `--no-renames` is REQUIRED: with a user's `diff.renames=true` (a common config),
    `git diff --name-only` reports a rename as ONLY the destination path, omitting the
    deleted source. The land then `git commit -- <new>` and never commits the staged
    DELETION of the old path → the renamed-away file lingers in HEAD and a staged
    deletion leaks into base for a later session's commit (Codex P1, data-loss).
    Disabling rename detection makes a rename always two entries (old delete + new
    add), so the scoped commit records both sides.

    `-z` is REQUIRED for the same reason `--no-renames` is: a non-ASCII / control-char
    filename in the diff is C-quoted under the default `core.quotepath=true`, and a
    quoted literal cannot be used to unstage / restore the real path (REVIEW-2026-06-21
    P1-1). NUL-delimited names are raw."""
    try:
        mb = _run(["git", "merge-base", branch, "HEAD"], cwd=base).stdout.strip()
        out = _run(
            ["git", "diff", "-z", "--name-only", "--no-renames", mb, branch], cwd=base
        ).stdout
    except RuntimeError:
        return []
    return _split_z(out)


def _scoped_conflict_cleanup(
    base: Path,
    touched: list[str],
    pre_untracked: set[str],
    preserve: set[str] | None = None,
) -> None:
    """Revert a failed `git merge --squash` touching ONLY the squash's own path
    set — a blanket `git reset --hard` / `git clean` would discard a concurrent
    editor's work on UNRELATED files (the merge fence does not lock external
    editors; Codex P0). Restores tracked paths to HEAD, then removes only the
    merge-introduced untracked files within that set (+ now-empty parent dirs).

    `preserve` = paths already STAGED/dirty in base BEFORE the squash (a concurrent
    session's forgiven `.claude/` / deliverable churn). When the task branch touches
    one of those SAME paths, `git merge --squash` aborts and `touched` includes the
    colliding path — resetting it to HEAD would clobber the concurrent session's
    staged work, re-opening the exact cross-session contamination class the scoped
    land defends against (REVIEW-2026-06-21 P1-2). Such paths are excluded from the
    reset/checkout/unlink, symmetric to how `pre_untracked` already protects
    pre-existing untracked files."""
    preserve = preserve or set()
    cleanup_paths = [p for p in touched if p not in preserve]
    if cleanup_paths:
        with contextlib.suppress(RuntimeError):
            _run(["git", "reset", "-q", "HEAD", "--", *cleanup_paths], cwd=base)
        # Per-path checkout: `git checkout -- a b` fails atomically if ANY path
        # is not in HEAD (a branch-added file), which would leave the others
        # un-restored — so restore each independently.
        for p in cleanup_paths:
            with contextlib.suppress(RuntimeError):
                _run(["git", "checkout", "-f", "HEAD", "--", p], cwd=base)
    for f in (_untracked_files(base) - pre_untracked) & set(cleanup_paths):
        path = base / f
        with contextlib.suppress(OSError):
            path.unlink()
        with contextlib.suppress(OSError):
            path.parent.rmdir()  # best-effort: drop a now-empty merge-introduced dir


def task_land(
    base_dir: Path,
    slug: str,
    *,
    message: str | None = None,
    session_uuid: str | None = None,
    allow_drift_land: bool = False,
) -> int:
    """ADR-003: squash-merge `hm/<slug>` onto the base branch + tear the task down.

    The ENTIRE critical section runs under the merge fence (flock primary +
    O_EXCL secondary, WSL2-reliable). The fence covers even distinct slugs
    because all lands serialize on the SHARED base HEAD/index (every land
    `git commit`s onto the same base branch). Order — each step individually
    idempotent so a re-run after a crash at ANY point converges without a double
    commit or an orphan:

    1. **(in-fence) branch re-check** — a concurrent same-slug winner may have
       landed + deleted the branch in the TOCTOU window since the pre-fence
       check; converge to a no-op rather than re-squash a gone branch (REVIEW
       concurrency C1).
    2. **base-cleanliness** — abort (`rc=1`, listing the files) on user dirt
       rather than clobber it (ADR-007 non-contact; `.claude/` churn excluded).
    3. **capture pending worktree work** — commit any uncommitted worktree edits
       onto the branch BEFORE the squash so the force-teardown can never lose
       them (the squash sees only committed branch work; REVIEW code P1).
    4. **idempotent squash** — skip when the branch already landed: the
       landed-marker == branch tip (robust even once base HEAD advances) OR
       `_branch_content_in_head` (content, not ancestry — squash-aware). Else
       `git merge --squash` + one conventional commit. On conflict, a SCOPED
       revert of only the squash's own path set (never a concurrent editor's
       unrelated work; REVIEW Codex P0) leaves base clean, branch preserved.
    5. **landed-marker** — written BEFORE teardown as the recovery anchor; a
       write failure aborts (`rc=1`) rather than tearing down anchorless.
    6. **teardown** — remove the worktree (skipped if gone), THEN delete the
       branch; a branch-delete failure aborts (`rc=1`, marker+row kept) so a
       non-converging orphan is never reported as success (REVIEW Codex P1).
       Then delete the landed-marker inline (the drain's sweep does not know the
       `hm/` namespace, so cleanup cannot depend on it).
    7. **registry row** — drop OUR row: uuid match when supplied, else (no uuid)
       only our-own-pid / a dead-pid row — a live mismatched-UUID/-pid row is
       never deleted (ADR-004; REVIEW Codex P1 / concurrency C2).

    The drain (`prune_stale`) runs AFTER the fence releases (best-effort,
    re-entrant) for general backlog hygiene — NOT load-bearing for this land's
    marker (deleted inline). Returns 0 on success or idempotent no-op, 1 on a
    base-dirty / conflict / inconsistent / partial abort with worktree+branch
    preserved.
    """
    if not _valid_task_slug(slug):
        # A force-removing entry point must validate at least as strictly as
        # task_create (REVIEW code P1: `..`/escape slug → path escape in teardown).
        print(f"[land] invalid task slug {slug!r}", file=sys.stderr)
        return 1
    base = base_dir.resolve()
    branch = task_branch(slug)
    wt = task_worktree_path(base, slug)
    own = session_uuid
    # The SHA of the squash commit THIS call freshly created — printed to stdout at the
    # end so wrapup's memory-fold anchors `--expect-head` on the exact in-fence squash,
    # not a post-hoc `rev-parse` a peer land could have advanced (REVIEW P2). Stays None on
    # every converge/already-landed/abort path, so stdout is empty unless a squash was made.
    landed_sha: str | None = None

    def _drop_own_row(rows: list[SessionRow]) -> list[SessionRow]:
        # ADR-004: never delete a LIVE mismatched row. Ours = uuid matches (when
        # supplied), else (no uuid) our-own-pid OR a dead pid (stale). A foreign
        # live-pid row on the same branch is PRESERVED (reclaimed later by its own
        # session). Leaking a row is the safe direction.
        out: list[SessionRow] = []
        for r in rows:
            if r.branch != branch:
                out.append(r)
                continue
            ours = (own is not None and r.session_uuid == own) or (
                own is None and (r.pid == os.getpid() or not _pid_alive(r.pid))
            )
            if not ours:
                out.append(r)
        return out

    def _converge_landed() -> None:
        _delete_landed_marker(base, branch)
        _registry_mutate(base, _drop_own_row)

    if not _branch_exists(base, branch):
        if not wt.is_dir():
            _converge_landed()  # fully-landed re-run → clear any leaked marker/row
            return 0
        print(
            f"[land] branch {branch} missing but worktree {wt} present — "
            "inconsistent; preserving for inspection",
            file=sys.stderr,
        )
        return 1

    # Default the squash message to the branch tip's curated commit message
    # (wrapup Step 7's why-message + Co-Authored-By) rather than a generic
    # placeholder — REVIEW-2026-06-21 P2-3. Computed here, BEFORE the fence and
    # `_capture_pending_in_worktree`, so the tip is the wrapup commit.
    msg = message or _branch_tip_message(base, branch) or f"chore({slug}): squash-land {branch}"
    try:
        with _acquire_merge_fence(base, timeout=_FENCE_TIMEOUT):
            # In-fence re-check: a concurrent winner may have deleted the branch
            # since the pre-fence check (TOCTOU). Converge instead of re-squashing.
            if not _branch_exists(base, branch):
                if wt.is_dir():
                    print(
                        f"[land] {branch} landed concurrently but worktree {wt} "
                        "remains — inconsistent; preserving for inspection",
                        file=sys.stderr,
                    )
                    return 1
                _converge_landed()
                return 0

            if _has_user_dirty_state(base):
                dirty = _list_user_dirty_files(base)
                print(
                    f"[land] base has uncommitted user changes — aborting land to "
                    f"avoid clobber: {dirty}",
                    file=sys.stderr,
                )
                return 1

            # Capture uncommitted worktree work onto the branch BEFORE the squash
            # so the force-teardown can't silently lose it (REVIEW code P1).
            if wt.is_dir():
                try:
                    if _capture_pending_in_worktree(wt):
                        print(
                            "[land] captured pending worktree work onto the branch before squash",
                            file=sys.stderr,
                        )
                except RuntimeError as e:
                    print(
                        f"[land] failed to capture pending worktree work: {e}; preserving worktree",
                        file=sys.stderr,
                    )
                    return 1

            # Already-landed: marker==tip survives later base-HEAD edits (Codex
            # P0); content-in-head is the fallback when no marker was written.
            already = _read_landed_marker(base, branch) == _branch_tip(
                base, branch
            ) or _branch_content_in_head(base, branch)
            if already:
                print(
                    f"[land] {branch} already landed — skipping squash "
                    "(idempotent partial-land re-run)",
                    file=sys.stderr,
                )
            else:
                touched = _squash_path_set(base, branch)
                if not touched:
                    # Empty path set in the NOT-already branch means the merge-base
                    # probe failed (unrelated histories) — `_branch_content_in_head`
                    # and `_squash_path_set` fail independently, so `already` can be
                    # False while `touched` is []. Do NOT `git merge --squash` here:
                    # on unrelated histories it would stage content we cannot scope to
                    # a path set, and we must NEVER reset the base index (a concurrent
                    # session may have staged work there). Abort rc1 — preserve the
                    # branch + worktree for manual resolution (code-reviewer P2).
                    print(
                        f"[land] cannot determine {branch}'s squash path set "
                        "(merge-base failure / unrelated histories?); preserving "
                        "branch + worktree for manual resolution",
                        file=sys.stderr,
                    )
                    return 1
                pre_untracked = _untracked_files(base)
                # Concurrent session's forgiven base churn staged BEFORE the squash:
                # must survive both a conflict-cleanup (P1-2) AND not land in our
                # commit (the count:3 contamination class).
                pre_staged = _staged_files(base)
                try:
                    _run(["git", "merge", "--squash", branch], cwd=base)
                    # Commit the squash's OWN path set from the INDEX — never the whole
                    # index, and never the WORKING TREE.
                    #
                    # `git commit -m msg` with NO pathspec would sweep a CONCURRENT
                    # session's pre-staged base churn (`.claude/` + deliverables are
                    # EXCLUDED by `_has_user_dirty_state`, so the base-dirty guard above
                    # does NOT abort on them) into our squash commit (the count:3 class;
                    # Codex P1). `git commit -m msg -- <touched>` (pathspec mode) avoided
                    # that but is PARTIAL-COMMIT mode: it records each path's WORKING-TREE
                    # blob, not the staged squash result, so an external editor touching a
                    # path in the squash→commit window would be committed instead — the
                    # fence does not lock external editors (REVIEW-2026-06-21 P2-1). It
                    # also broke on non-ASCII names (P1-1).
                    #
                    # Instead: UNSTAGE the concurrent churn (paths staged that are NOT in
                    # `touched`), leaving the index == HEAD + the squash's touched paths,
                    # then a plain `git commit` records the INDEX. The unstaged churn stays
                    # in the working tree (preserved, not lost, not ours) for its owning
                    # session to re-stage; no working-tree read, no pathspec quoting.
                    staged_after = _staged_files(base)
                    if not (staged_after & set(touched)):
                        # The 3-way merge resolved EVERY touched path to base HEAD content
                        # (the branch's change is already present in HEAD via a prior land /
                        # cherry-pick / subset edit), so the squash staged nothing of ours —
                        # there is genuinely nothing to land. `_branch_content_in_head` missed
                        # this (per-blob mismatch vs the actual 3-way result), leaving
                        # `already` False. Converge to teardown instead of letting
                        # `git commit` fail "nothing to commit" and mis-route to the conflict
                        # path, which would NEVER converge — branch + worktree + registry row
                        # would leak indefinitely (REVIEW-2026-06-21 P2-2). Leave any
                        # concurrent churn staged exactly as found (do NOT touch the index).
                        print(
                            f"[land] {branch}'s changes are already present in HEAD "
                            "(squash is empty) — converging to teardown",
                            file=sys.stderr,
                        )
                    else:
                        # ADR-002 land drift-block: the squash DID stage real
                        # divergent work, so this branch has un-landed content
                        # developed against a base that has since advanced. Refuse
                        # unless --allow-drift-land. Placed here — AFTER the
                        # already-landed convergence check (Codex P1) AND after the
                        # empty-squash no-op converges above — so a partial-land
                        # re-run or an already-present change is NEVER drift-blocked.
                        # Scoped-cleanup restores base so it is left untouched.
                        behind, _ahead = _branch_drift(base, branch)
                        if behind > 0 and not allow_drift_land:
                            _scoped_conflict_cleanup(
                                base, touched, pre_untracked, preserve=pre_staged
                            )
                            print(
                                f"[land] {branch} is {behind} commit(s) behind the base "
                                f"tip with un-landed work; run `task-refresh {slug}` then "
                                "re-land, or pass --allow-drift-land. Base + branch "
                                "left untouched.",
                                file=sys.stderr,
                            )
                            return 1
                        to_unstage = sorted(staged_after - set(touched))
                        if to_unstage:
                            _run(["git", "reset", "-q", "HEAD", "--", *to_unstage], cwd=base)
                        _run(["git", "commit", "-m", msg], cwd=base)
                        landed_sha = _run(["git", "rev-parse", "HEAD"], cwd=base).stdout.strip()
                except RuntimeError as e:
                    _scoped_conflict_cleanup(base, touched, pre_untracked, preserve=pre_staged)
                    print(
                        f"[land] squash-merge of {branch} failed (conflict?); base "
                        f"reset clean, branch preserved for manual resolution: {e}",
                        file=sys.stderr,
                    )
                    return 1

            # Recovery anchor BEFORE teardown — NOT best-effort: without it a
            # crash mid-teardown could not be recognized as already-landed.
            try:
                _write_landed_marker(base, branch)
            except RuntimeError as e:
                print(
                    f"[land] landed-marker write failed; preserving for re-run: {e}",
                    file=sys.stderr,
                )
                return 1

            if wt.is_dir():
                try:
                    cleanup(wt, on_success=True)
                except RuntimeError as e:
                    print(
                        f"[land] worktree cleanup failed (squash already in HEAD; "
                        f"re-run to finish teardown): {e}",
                        file=sys.stderr,
                    )
                    return 1
            try:
                _run(["git", "branch", "-D", branch], cwd=base)
            except RuntimeError as e:
                # Do NOT report success on a non-converging orphan (Codex P1).
                # Keep marker + row so a re-run finishes the teardown.
                print(
                    f"[land] branch delete failed (squash already landed; re-run to "
                    f"finish teardown): {e}",
                    file=sys.stderr,
                )
                return 1
            # Marker's recovery role is done — delete inline (the drain's sweep
            # does not recognize the `hm/` namespace, so it would otherwise leak).
            _delete_landed_marker(base, branch)
            _registry_mutate(base, _drop_own_row)
    except (RuntimeError, TimeoutError) as e:
        print(
            f"[land] fence/land failed, preserving worktree + branch for re-run: {e}",
            file=sys.stderr,
        )
        return 1

    # Drain AFTER the fence releases (general backlog hygiene; best-effort —
    # NOT load-bearing for this land's marker, already deleted inline above).
    with contextlib.suppress(Exception):
        prune_stale(base)
    # Stdout contract (REVIEW P2): the fresh-squash SHA on its own line, ONLY when this
    # call created it. Every diagnostic above goes to stderr, so stdout is empty on the
    # converge/already-landed paths — wrapup reads this to decide whether to fold + what
    # to anchor `--expect-head` on, without a race-prone second `rev-parse`.
    if landed_sha is not None:
        print(landed_sha)
    return 0


def _cli_task_create(args: list[str]) -> int:
    """`python -m harness_maker.worktree task-create <slug> [base_dir]` (ADR-002/006)."""
    rest = [a for a in args if not a.startswith("--")]
    if not rest:
        print("usage: task-create <slug> [base_dir]", file=sys.stderr)
        return 2
    slug = rest[0]
    base = Path(rest[1]).resolve() if len(rest) > 1 else Path.cwd()
    allow_shared = "--allow-shared-slug" in args
    try:
        wt = task_create(base, slug, session_uuid=uuid.uuid4().hex[:12], allow_shared=allow_shared)
    except SharedSlugError as exc:
        print(f"[task-create] {exc}", file=sys.stderr)
        return 1
    print(str(wt))
    return 0


# The human memory outputs wrapup writes to the BASE repo (memory_md._base_root strips
# the .worktrees/<slug> suffix). The machine tiers (semantic/episodic/profile) are churn
# and deliberately excluded.
#
# There are TWO writers, and only one used to be represented here. `memory_md` writes
# wiki/failures/session; the wrapup STAGE additionally writes `pending-proposals.md`
# (Step 5.3, a MUST step) and `pending-drift.md` by hand. The old allowlist was derived
# from memory_md's targets alone — and its correspondence test asserted only that — so
# the two hand-written files were never folded into the squash and sat as base dirt
# forever. Nothing broke loudly: the create-guard forgives `.claude/memory/`, so the
# escalation output the whole count>=3 machinery exists to produce simply never reached
# git, and never existed for a fresh clone or a collaborator.
#
# `test_wrapup_memory_fold.test_tier_pathspec_covers_every_memory_output_wrapup_writes`
# now derives the expected set from BOTH writers, including a scan of the rendered
# stage, so adding a third memory output fails until the fold covers it.
# PLAN-harness-diet ADR-005: `upsert-failure`'s archive pass is a THIRD memory writer, and
# it is the one whose omission is worst — an eviction removes entries from the tracked
# `failures.md` and writes them to `archive/`, so a fold that skips `archive/` turns
# "archive, never delete" into a delete with no replacement committed. Exactly the failure
# the comment above records for pending-proposals/pending-drift, one tier further down.
_HUMAN_MEMORY_TIER_PATHSPEC: tuple[str, ...] = (
    ".claude/memory/wiki.md",
    ".claude/memory/failures.md",
    ".claude/memory/pending-proposals.md",
    ".claude/memory/pending-drift.md",
    ".claude/memory/session",
    ".claude/memory/archive",
)

_HUMAN_MEMORY_TIER_FILES: frozenset[str] = frozenset(
    p for p in _HUMAN_MEMORY_TIER_PATHSPEC if p.endswith(".md")
)


def _is_human_memory_tier_path(rel: str) -> bool:
    """WHY: scope the fold to the exact human tiers, never a machine-churn path."""
    rel = rel.strip()
    if rel in _HUMAN_MEMORY_TIER_FILES:
        return True
    if rel.startswith(".claude/memory/archive/") and rel.endswith(".md"):
        return True
    return rel.startswith(".claude/memory/session/") and rel.endswith(".md")


def commit_base_memory(base: Path, expect_head: str) -> int:
    """Fold the human memory tiers into the fresh squash commit (ADR-001/004; ADR-003 rev).

    Memory is written to the BASE repo, so after `task-land` it sits as base working-tree
    dirt outside the squash's path set — never committed. This amends it into the squash.
    Both tracked-modified AND untracked tiers are folded, but ONLY paths inside the human-
    tier pathspec — an untracked path outside it is never newly tracked (narrow-filter).

    Accepted limitation (REVIEW P3): wiki/failures/session-<date> are cross-session SHARED
    base files. A peer's UN-fenced memory append (wrapup Step 5) landing between the
    `ls-files` and the `git add -f` here can be co-staged into this commit. It is append-
    only / non-destructive (the peer's lines are preserved; only their commit attribution
    differs), so it is not hardened. The safety argument for this fold is the amend fence +
    `--only` pathspec, NOT a 'single session owns its memory writes' invariant — that
    invariant is false for these shared dated files.

    The amend is gated (ADR-004) and concurrency-fenced (REVIEW): the check->add->amend
    runs under the same `index.lock-hm` merge fence task_land uses, re-asserts HEAD ==
    expect_head INSIDE the fence, and amends with `--only -- <memory pathspec>`. So a
    converge/no-op land, a peer that advances base HEAD mid-amend, or a peer that stages
    foreign churn into the shared base index can never be folded into the wrong commit
    (the count:3 'finalize-pulls-orphan-wip-into-main' contamination class).
    """
    base = Path(base)

    def _git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 — args list, no shell
            ["git", *args],
            cwd=str(base),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )

    head = _git("rev-parse", "HEAD")
    if head.returncode != 0:
        print(f"[commit-base-memory] cannot read HEAD: {head.stderr.strip()}", file=sys.stderr)
        return head.returncode or 1
    if head.stdout.strip() != expect_head:
        print(
            f"[commit-base-memory] refusing: HEAD {head.stdout.strip()} is not the expected "
            f"fresh squash {expect_head} — not amending",
            file=sys.stderr,
        )
        return 1

    # The check->add->amend critical section runs under the SAME merge fence task_land
    # uses (index.lock-hm), so a concurrent session's fenced squash cannot stage into the
    # shared base index or advance HEAD mid-amend (REVIEW: unfenced amend race, count:3
    # 'finalize-pulls-orphan-wip-into-main' class). Inside the fence we (a) re-assert HEAD
    # == expect_head — a peer could have landed between the pre-check and fence acquisition,
    # and `git commit --amend` rewrites *current* HEAD, so amending a peer's commit must be
    # impossible — and (b) scope the amend to the memory pathspec via `--only`, so even a
    # residual foreign staged entry is structurally never swept into this commit.
    fold: list[str] = []
    try:
        with _acquire_merge_fence(base, timeout=_FENCE_TIMEOUT):
            head = _git("rev-parse", "HEAD")
            if head.returncode != 0 or head.stdout.strip() != expect_head:
                print(
                    f"[commit-base-memory] refusing: HEAD moved to {head.stdout.strip()} under "
                    f"the fence (expected {expect_head}) — not amending",
                    file=sys.stderr,
                )
                return 1

            staged = [
                ln
                for ln in _git("diff", "--cached", "--name-only").stdout.splitlines()
                if ln.strip()
            ]
            foreign = [s for s in staged if not _is_human_memory_tier_path(s)]
            if foreign:
                print(
                    f"[commit-base-memory] refusing: non-memory content already staged: "
                    f"{foreign} — not amending",
                    file=sys.stderr,
                )
                return 1

            # Fold tracked-modified human tiers AND untracked ones that fall INSIDE the tier
            # pathspec (ADR-003 revised): memory_md creates today's session/<date>.md fresh
            # (and wiki/failures on a greenfield base), so they are untracked-and-ignored on
            # first write — `ls-files -m` misses them and the seam this fix targets would
            # persist for the richest per-task tier. `--others` (no --exclude-standard) lists
            # untracked INCLUDING gitignored; the `_is_human_memory_tier_path` filter keeps the
            # force-add strictly bounded to the tier — an untracked path OUTSIDE it is never
            # newly tracked (the narrow-filter invariant the original ADR-003 protected).
            tracked_mod = [
                p
                for p in _git(
                    "ls-files", "-m", "--", *_HUMAN_MEMORY_TIER_PATHSPEC
                ).stdout.splitlines()
                if p.strip() and _is_human_memory_tier_path(p)
            ]
            untracked_tier = [
                p
                for p in _git(
                    "ls-files", "--others", "--", *_HUMAN_MEMORY_TIER_PATHSPEC
                ).stdout.splitlines()
                if p.strip() and _is_human_memory_tier_path(p)
            ]
            to_add = sorted(set(tracked_mod) | set(untracked_tier))
            if to_add:
                add = _git("add", "-f", "--", *to_add)
                if add.returncode != 0:
                    print(
                        f"[commit-base-memory] git add failed: {add.stderr.strip()}",
                        file=sys.stderr,
                    )
                    return add.returncode

            fold = [
                ln
                for ln in _git("diff", "--cached", "--name-only").stdout.splitlines()
                if ln.strip() and _is_human_memory_tier_path(ln.strip())
            ]
            if not fold:
                print("[commit-base-memory] no tracked memory changes to fold (no-op)")
                return 0

            # `--only -- <memory paths>` builds the amended commit from HEAD's tree plus ONLY
            # these paths, disregarding any other staged entry — airtight against sweep-in.
            amend = _git("commit", "--amend", "--no-edit", "--only", "--", *fold)
            if amend.returncode != 0:
                print(amend.stderr.strip() or amend.stdout.strip(), file=sys.stderr)
                return amend.returncode
    except (RuntimeError, TimeoutError) as exc:
        # Mirror task_land's fence error handling (REVIEW P2): a 360s fence-contention
        # timeout or gitdir-resolve failure degrades gracefully — the memory is still on
        # disk as base dirt and a re-run folds it once the contending session releases.
        print(
            f"[commit-base-memory] could not acquire the base merge fence ({exc}) — memory "
            "left as base dirt; re-run after the contending session finishes",
            file=sys.stderr,
        )
        return 1

    # Every human tier inside the pathspec — tracked-modified or untracked — is folded
    # (ADR-003 revised), so there is no longer a skipped-untracked class to report.
    print(f"[commit-base-memory] folded {len(fold)} tier(s): {', '.join(fold)}")
    return 0


def _cli_commit_base_memory(args: list[str]) -> int:
    """`worktree commit-base-memory <base> --expect-head <sha>` — fold memory (ADR-001)."""
    expect_head: str | None = None
    rest: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--expect-head":
            if i + 1 >= len(args):
                print("usage: commit-base-memory <base> --expect-head <sha>", file=sys.stderr)
                return 2
            expect_head = args[i + 1]
            i += 2
            continue
        if args[i].startswith("--"):
            i += 1
            continue
        rest.append(args[i])
        i += 1
    if not rest or expect_head is None:
        print("usage: commit-base-memory <base> --expect-head <sha>", file=sys.stderr)
        return 2
    return commit_base_memory(Path(rest[0]).resolve(), expect_head=expect_head)


def _cli_task_land(args: list[str]) -> int:
    """`python -m harness_maker.worktree task-land <slug> [base_dir] [--message <m>]` (ADR-003)."""
    message: str | None = None
    rest: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--message":
            if i + 1 >= len(args):
                print("usage: task-land <slug> [base_dir] [--message <m>]", file=sys.stderr)
                return 2
            message = args[i + 1]
            i += 2
            continue
        if args[i].startswith("--"):
            i += 1  # other flags (e.g. --allow-drift-land) are not positional
            continue
        rest.append(args[i])
        i += 1
    if not rest:
        print("usage: task-land <slug> [base_dir] [--message <m>]", file=sys.stderr)
        return 2
    slug = rest[0]
    base = Path(rest[1]).resolve() if len(rest) > 1 else Path.cwd()
    allow_drift_land = "--allow-drift-land" in args
    return task_land(base, slug, message=message, allow_drift_land=allow_drift_land)


def _flag_value(args: list[str], flag: str) -> str | None:
    """`--flag value` and `--flag=value`, both forms."""
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args):
            return args[i + 1]
        if a.startswith(f"{flag}="):
            return a.split("=", 1)[1]
    return None


def _positionals(args: list[str], *, valued_flags: tuple[str, ...]) -> list[str]:
    """Positionals with each valued flag's VALUE consumed, not mistaken for one."""
    out: list[str] = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            skip = a in valued_flags  # `--flag=value` carries its own value
            continue
        out.append(a)
    return out


def _span_end_session_id() -> str | None:
    """The caller's Claude session id, from the channel this command actually has.

    `span-end` ships ONLY as a `Stop` / `PreCompact` hook (both settings templates),
    and a hook's session id arrives on **stdin** — `hooks/sessionid_envfile.py` says so
    in as many words ("The Stop-hook DOES receive `session_id` on stdin, but the loop
    driver/marker writer (a slash command) does not"), and the sibling Stop hook
    `hooks/loop_gate.py` reads it from there. `HM_SESSION_ID` is the *slash-command*
    bridge and it is **unexported**, so a Python hook process never sees it at all —
    on any platform, not merely "empty on WSL2" as this once said
    (PLAN-sessionid-env-propagation ADR-003).

    Reading only the env var was therefore the wrong channel (review round 3): when the
    hook process has no `HM_SESSION_ID` but the `start` carried one, the caller matches
    none of its own events, writes no `end`, and the span stays open until a cap fires —
    the unbounded over-attribution ADR-003 rejected start-only closure to avoid.

    stdin first (authoritative for a hook), env second (a direct CLI invocation).
    """
    from .loop_marker import sanitize_session_id

    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip():
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    sid = payload.get("session_id")
                    if isinstance(sid, str) and sid.strip():
                        return sanitize_session_id(sid) or None
    except Exception:  # noqa: BLE001 - a hook must never fail on a malformed payload
        pass
    env = os.environ.get("HM_SESSION_ID")
    return (sanitize_session_id(env) or None) if env else None


def _cli_span_end(args: list[str]) -> int:
    """`worktree span-end [base_dir] [--stage <s>]` — close the open span.

    Wired to the Stop / PreCompact hooks, which is why it must be a no-op when no
    span is open: those hooks fire on EVERY session, including ones that ran no
    `/hm:` stage. A bare `end` written then would be paired by the reader against
    whatever span preceded it — possibly from a different session entirely.

    Claude-Code-only by construction: hooks live in `.claude/settings.json`, which
    only Claude Code reads. On Cursor/Codex spans close by next-start or cap
    (ADR-003), which is why those targets should expect a higher `capped_turns`.
    """
    stage = _flag_value(args, "--stage")
    rest = _positionals(args, valued_flags=("--stage",))
    base = Path(rest[0]).resolve() if rest else Path.cwd()
    try:
        from .stage_spans import emit_event, ledger_path, read_events

        events, _ = read_events(ledger_path(base))
        # Look at the last event OF THE CALLER'S SESSION, not the globally-last line
        # (review R2-03). The ledger is SHARED, so with two sessions active any peer
        # append made the old `events[-1]` tests fire and this session's `end` was
        # never written. That used to be masked: the reader closed the globally-current
        # span on any start, so a peer's start closed your span as a side effect. Once
        # `_build_spans` was partitioned by session (F-02) nothing closed it at all —
        # the span stayed open until a cap fired, which is precisely the unbounded
        # over-attribution ADR-003 rejected start-only closure to avoid.
        mine = _span_end_session_id()
        if mine:
            ours = [e for e in events if e.session_id == mine]
        else:
            # Degraded (no id of our own): fall back to the session-less events, which
            # is the same rule the loop marker uses — never let an id-bearing peer's
            # line decide for us, and never close an id-bearing peer's span.
            #
            # KNOWN LIMIT: two CONCURRENT id-less sessions share this bucket, so one
            # can close the other's span. There is no per-session key to separate them
            # (that is what having no id means), and the alternative — never closing an
            # id-less span — leaves it open to the cap, which is worse. Structurally
            # unavoidable, same as the loop marker's id-less case.
            ours = [e for e in events if e.session_id is None]
        if not ours or ours[-1].event == "end":
            return 0  # nothing of ours is open — see docstring
        emit_event("end", stage=stage or ours[-1].stage, cwd=base, session_id=mine)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[span] end emission failed (non-fatal): {exc}", file=sys.stderr)
    return 0


def _cli_task_preflight(args: list[str]) -> int:
    """`python -m harness_maker.worktree task-preflight <slug> [base_dir] [--stage <s>]`.

    Prints the task worktree path to stdout (for `<WT>` capture) and any
    preflight warnings (active sessions, drift) to stderr."""
    stage = _flag_value(args, "--stage")
    claude_sid = _flag_value(args, "--claude-session-id")
    # Flag-AWARE positional split (ADR-008). The old `[a for a in args if not
    # a.startswith("--")]` treated a flag's VALUE as a positional, so
    # `task-preflight <slug> --stage hm:plan "$(pwd)"` resolved base_dir to
    # Path("hm:plan") — creating the worktree under a directory named after the
    # stage and writing the ledger to the wrong root.
    rest = _positionals(args, valued_flags=("--stage", "--claude-session-id"))
    if not rest:
        print("usage: task-preflight <slug> [base_dir] [--stage <stage>]", file=sys.stderr)
        return 2
    slug = rest[0]
    base = Path(rest[1]).resolve() if len(rest) > 1 else Path.cwd()
    allow_shared = "--allow-shared-slug" in args
    try:
        wt, warnings = task_preflight(
            base,
            slug,
            session_uuid=uuid.uuid4().hex[:12],
            allow_shared=allow_shared,
            stage=stage,
            claude_session_id=claude_sid,
        )
    except SharedSlugError as exc:
        # ADR-001: a foreign LIVE session holds this task branch. Hard-fail with
        # the escape-hatch hint rather than silently sharing the worktree.
        print(f"[preflight] {exc}", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError) as exc:
        # ValueError = bad slug; RuntimeError = a failed git op surfaced by `_run`
        # (non-git base dir, `git worktree add` failure). Return a controlled rc,
        # never a traceback (REVIEW Codex P2).
        print(f"[preflight] {exc}", file=sys.stderr)
        return 1
    for w in warnings:
        print(w, file=sys.stderr)
    print(str(wt))
    return 0


def _cli_task_refresh(args: list[str]) -> int:
    """`python -m harness_maker.worktree task-refresh <slug> [base_dir]` (Phase 5)."""
    rest = [a for a in args if not a.startswith("--")]
    if not rest:
        print("usage: task-refresh <slug> [base_dir]", file=sys.stderr)
        return 2
    slug = rest[0]
    base = Path(rest[1]).resolve() if len(rest) > 1 else Path.cwd()
    return task_refresh(base, slug)


def _drain(base_dir: Path) -> PruneReport:
    """ADR-009 drain trigger: the gated, biased-to-preserve sweep, off the create path.

    Reuses `prune_stale` (the single gate) so /hm:wrapup and /hm:health can drain the
    backlog. Create-time reaping in `_cli_create` is RETAINED additively — this only
    ADDS off-create entry points, it does not move the create-time call.
    """
    return prune_stale(base_dir)


def _drain_summary(report: PruneReport) -> str:
    """One-line, non-interactive summary for the wrapup/health drain (ADR-009).

    Unlike `prune-branches`, this never nags to re-run with --force — the drain is
    automatic and biased-to-preserve, so preserved items surface as a count only.
    """
    preserved = len(report.preserved_branches) + len(report.preserved_stash_refs)
    return (
        f"worktree drain: removed {len(report.removed_branches)} branch(es), "
        f"{len(report.removed_landed_markers)} marker(s), "
        f"{len(report.removed_stash_refs)} stash-ref(s); "
        f"{preserved} preserved (run `prune-branches` to review)"
    )


def _cli_drain(args: list[str]) -> int:
    """`python -m harness_maker.worktree drain [base_dir]` — ADR-009 drain trigger."""
    rest = [a for a in args if not a.startswith("--")]
    base = Path(rest[0]).resolve() if rest else Path.cwd()
    print(_drain_summary(_drain(base)))
    return 0


def _cli_loop_mode_active(args: list[str]) -> int:
    """`worktree loop-mode-active <base> --claude-session-id <id>` — exit 0 if in a loop.

    Session-scoped loop-mode detection for the stage templates (plan / banners):
    exit 0 ("active") iff some ``.claude/.hm-loop-*`` marker's content header
    matches this session's id, OR a legacy global ``.hm-loop-active`` exists
    (degraded fallback). Exit 1 ("inactive") otherwise. The session id distinguishes
    a loop (loop.md.j2 passes ``--claude-session-id``) from a standalone worktree
    (empty header). PLAN-loop-marker-session-scoping ADR-002/003.
    """
    from harness_maker.loop_marker import marker_dir_has_session, sanitize_session_id

    claude_session_id = ""
    if "--claude-session-id" in args:
        idx = args.index("--claude-session-id")
        if idx + 1 >= len(args):
            print("loop-mode-active: --claude-session-id requires a value", file=sys.stderr)
            return 2
        claude_session_id = args[idx + 1]
        del args[idx : idx + 2]
    if len(args) != 1:
        print("usage: loop-mode-active <base> --claude-session-id <id>", file=sys.stderr)
        return 2
    base = Path(args[0]).resolve()
    sid = sanitize_session_id(claude_session_id)
    # Content-match is session-scoped. The legacy global is honored ONLY when
    # THIS session has no id (degraded) — a valid-id session must NOT be pulled
    # into loop-mode by another session's degraded global marker (re-review C1:
    # bug-2 would otherwise survive in the degraded path for valid-id sessions).
    if marker_dir_has_session(base / _LOOP_MARKER_DIR, sid) or (
        not sid and (base / ".hm-loop-active").exists()
    ):
        print("active")
        return 0
    print("inactive")
    return 1


def main(argv: list[str] | None = None) -> int:
    """Dispatch worktree subcommand from argv."""
    _guard = command_registry.guard_or_none("worktree", argv)
    if _guard is not None:
        return _guard
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "usage: python -m harness_maker.worktree "
            "<create|verify|finalize|post-commit-pop|owned-uuids|wt-uuid|"
            "owned-crumb-add|owned-crumb-read|owned-crumb-clear|cleanup-all|"
            "prune-branches|drain|task-create|task-land|task-preflight|"
            "task-refresh> [...]",
            file=sys.stderr,
        )
        return 2
    sub, rest = args[0], args[1:]
    if sub == "create":
        return _cli_create(rest)
    if sub == "verify":
        return _cli_verify(rest)
    if sub == "finalize":
        return _cli_finalize(rest)
    if sub == "post-commit-pop":
        return _cli_post_commit_pop(rest)
    if sub == "owned-uuids":
        return _cli_owned_uuids(rest)
    if sub == "wt-uuid":
        return _cli_wt_uuid(rest)
    if sub == "owned-crumb-add":
        return _cli_owned_crumb_add(rest)
    if sub == "owned-crumb-read":
        return _cli_owned_crumb_read(rest)
    if sub == "owned-crumb-clear":
        return _cli_owned_crumb_clear(rest)
    if sub == "cleanup-all":
        return _cli_cleanup_all(rest)
    if sub == "prune-branches":
        return _cli_prune_branches(rest)
    if sub == "drain":
        return _cli_drain(rest)
    if sub == "task-create":
        return _cli_task_create(rest)
    if sub == "task-land":
        return _cli_task_land(rest)
    if sub == "commit-base-memory":
        return _cli_commit_base_memory(rest)
    if sub == "task-preflight":
        return _cli_task_preflight(rest)
    if sub == "task-refresh":
        return _cli_task_refresh(rest)
    if sub == "span-end":
        return _cli_span_end(rest)
    if sub == "loop-mode-active":
        return _cli_loop_mode_active(rest)
    print(f"unknown subcommand: {sub}", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess
    sys.exit(main())
