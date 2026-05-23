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
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_maker.io_utils import atomic_write, load_harness_yaml

# Used by both stash list SHA capture and ref-file validation (ADR-002).
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# Anchors the session_marker absolute-path regex (ADR-002): leading `/`,
# followed by some directory chain, then `/.claude/.hm-loop-<wt-name>`.
_SESSION_MARKER_RE = re.compile(r"^/.+/\.claude/\.hm-loop-[A-Za-z0-9_.-]+$")

WORKTREE_DIR_NAME = ".worktrees"
_TS_FMT = "%Y%m%dT%H%MZ"
_GIT_TIMEOUT = 60  # seconds — prevent hang on SSH prompt or NFS stall
# Longer timeout for `git stash push -u` on large working trees with untracked
# binary artifacts. Bumped per REVIEW M-P1-3 — 60s was tight for repos >100MB.
_GIT_TIMEOUT_LONG = 300

# Per-session marker files: .claude/.hm-loop-{primary-wt-basename}
# One file per active session — parallel sessions coexist without collision.
# Gate reads all matching files via glob. Finalize deletes only its own file.
_LOOP_MARKER_DIR = Path(".claude")
_LOOP_MARKER_PREFIX = ".hm-loop-"
_LOOP_MARKER_GITIGNORE_PATTERN = ".claude/.hm-loop-*"


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
        # Rollback: remove all already-created worktrees (including primary) so no
        # orphaned git worktrees accumulate without a marker or manual-cleanup path.
        for created_wt, sib in zip(sibling_wts, siblings[: len(sibling_wts)], strict=False):
            with contextlib.suppress(RuntimeError):
                _run(["git", "worktree", "remove", "--force", str(created_wt)], cwd=sib)
        with contextlib.suppress(RuntimeError):
            _run(["git", "worktree", "remove", "--force", str(primary_wt)], cwd=base)
        raise

    all_wts = [primary_wt, *sibling_wts]
    _write_loop_marker(base, primary_wt.name, all_wts)
    return all_wts


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
    Cleanup --force may delete a Cursor write that arrived after our status
    check but before our git add. CLAUDE.md "Worktree 공유" notes the prefix-
    match cleanup boundary; in practice harness-maker and Cursor own different
    worktree prefixes, so the actual race surface is small.
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
)


def _is_harness_artifact(porcelain_line: str) -> bool:
    """Return True if a porcelain status line refers to a path we manage.

    Porcelain v1 format: ``XY path`` where XY is a 2-char status code and the
    path starts at column 3. Harness-managed paths are excluded from the
    "is base dirty" check so users who don't gitignore ``.worktrees/`` etc.
    don't see spurious stash activity (the artifacts get carried by the stash
    anyway when real user dirty is present; we just don't TRIGGER on them).
    """
    if len(porcelain_line) < 4:
        return False
    path = porcelain_line[3:].strip()
    # Rename entries can have "from -> to"; consider the destination.
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    # Strip optional quote wrapping that git adds for paths with special chars.
    path = path.strip('"')
    return path.startswith(_HARNESS_ARTIFACT_PREFIXES)


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
    for line in listing.stdout.splitlines():
        # Each line is `<40-char sha> <subject>`. Subject often has the form
        # `On main: <message>`; some git versions include the branch prefix
        # in %gs output, others don't. Match by message suffix to handle both.
        if not line:
            continue
        sha, _, subject = line.partition(" ")
        if len(sha) != 40 or not _SHA_RE.match(sha):
            continue
        # Match either the bare message or the "On <branch>: <message>" form.
        if subject.endswith(f": {message}") or subject == message:
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
    """Count `.hm-finalize-stash-*` ref files in `<base>/.claude/`.

    PLAN-worktree-cross-session-data-loss-defense ADR-003 queue-guard:
    `worktree create` ABORTs when ≥2 such refs exist, because that's the
    canonical "wrapup not run between exec-rev turns" footgun signature.
    Missing dir → 0 (clean state).
    """
    if not claude_dir.is_dir():
        return 0
    return sum(1 for _ in claude_dir.glob(f"{_STASH_REF_PREFIX}*"))


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
    if _is_harness_artifact(porcelain_line):
        return True
    # Extract path after the 2-char XY status + space.
    if len(porcelain_line) > 3:
        path = porcelain_line[3:].strip()
        # Handle rename arrow `old -> new`: check the right-hand side.
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        # Strip surrounding quotes that git adds for paths with special chars.
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if path.startswith(".claude/") or path == ".claude":
            return True
    return False


def _has_user_dirty_state(base: Path) -> bool:
    """True iff `git status --porcelain` shows USER-owned dirt (not harness).

    PLAN-worktree-cross-session-data-loss-defense ADR-002 dirty-base guard:
    `worktree create` ABORTs when base has uncommitted USER changes — the
    canonical 'finalize-pulls-orphan-wip-into-main' setup ([fail:design]
    count:2 → 3rd 2026-05-23). Filter via `_is_create_guard_harness_artifact`
    which excludes `.claude/` entirely (real users gitignore it).
    """
    try:
        status = _run(["git", "status", "--porcelain"], cwd=base)
    except RuntimeError:
        return False  # Not a git repo or git unavailable — let downstream fail naturally.
    user_lines = [
        line for line in status.stdout.splitlines() if not _is_create_guard_harness_artifact(line)
    ]
    return bool(user_lines)


def _list_user_dirty_files(base: Path) -> list[str]:
    """Return the user-dirty filenames for the abort-message listing."""
    try:
        status = _run(["git", "status", "--porcelain"], cwd=base)
    except RuntimeError:
        return []
    out: list[str] = []
    for line in status.stdout.splitlines():
        if _is_create_guard_harness_artifact(line):
            continue
        if len(line) > 3:
            out.append(line[3:].strip())
    return out


def _list_pending_stash_refs(claude_dir: Path) -> list[str]:
    """Return ref-file basenames for the abort-message listing."""
    if not claude_dir.is_dir():
        return []
    return sorted(p.name for p in claude_dir.glob(f"{_STASH_REF_PREFIX}*"))


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


def _excl_lock(lock_path: Path, timeout: float) -> int:
    """O_EXCL polling lock — reliable on WSL2/NTFS when flock isn't.

    Returns the fd holding the lock; caller must close it AND unlink the
    lock file to release. Polls every 50ms until acquired or timeout.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            return os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"merge fence O_EXCL timeout after {timeout}s on {lock_path}"
                ) from None
            time.sleep(0.05)


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


@contextlib.contextmanager
def _acquire_merge_fence(base: Path, timeout: float = 60.0):  # type: ignore[no-untyped-def]
    """Serialize the merge step across parallel finalize invocations.

    PLAN-worktree-cross-session-data-loss-defense ADR-005. Primary path:
    fcntl.flock on `<base>/.git/index.lock-hm`. Secondary (equal-status,
    NOT silent skip) when flock is unavailable: O_EXCL polling lock on
    `<base>/.git/index.lock-hm-excl`. Either path works on WSL2/NTFS.

    Lock file is harness-owned — must be excluded from dirty-base guard
    via `_HARNESS_ARTIFACT_PREFIXES` already (`.git/` is gitignored).
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
    flock_path = lock_dir / "index.lock-hm"
    excl_path = lock_dir / "index.lock-hm-excl"

    fd, mechanism = _flock_lock(flock_path, timeout)
    if mechanism == "unsupported":
        # Secondary mechanism: O_EXCL atomic create
        fd = _excl_lock(excl_path, timeout)
        try:
            yield
        finally:
            os.close(fd)
            with contextlib.suppress(FileNotFoundError):
                excl_path.unlink()
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
    # isolation). Falls back to project-scoped helper when wt_name has no UUID
    # (legacy create() pre-dirname-embed produced bare timestamps); in that
    # case isolation degrades to "shared project UUID" but the call path
    # remains functional.
    dirname_uuid = _extract_uuid_from_wt_name(wt_name)
    effective_uuid = session_uuid or dirname_uuid or _current_session_uuid(base)
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


def _scope_includes(harness_yaml: Path, stage: str) -> bool:
    """Read harness.yaml; return True iff worktree.scope includes the stage."""
    try:
        data = load_harness_yaml(harness_yaml)
    except (OSError, yaml.YAMLError):
        return False
    wt = data.get("worktree")
    if not isinstance(wt, dict):
        return False
    scope = wt.get("scope")
    return isinstance(scope, list) and stage in scope


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
    args = [a for a in args if a not in ("--allow-stash-queue", "--allow-dirty-base")]

    if len(args) != 2:
        print(
            "usage: create <stage> <base_dir> [--allow-stash-queue] [--allow-dirty-base]",
            file=sys.stderr,
        )
        return 2
    stage, base_str = args
    base = Path(base_str).resolve()

    existing = _detect_existing_worktree(base)
    if existing is not None:
        # Already inside a worktree; marker should already be in place from
        # the parent loop's create. No-op idempotent return.
        print(str(existing))
        return 0

    # ADR-003 queue-guard (must run BEFORE scope check so a misconfigured
    # base still surfaces the guard message — failure mode visibility):
    claude_dir = base / _LOOP_MARKER_DIR
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
    if not _scope_includes(yaml_path, stage):
        print("")
        return 0

    # Load sibling_repos from harness.yaml (empty list when field absent)
    sibling_dirs = _load_sibling_dirs(yaml_path, base)

    wt_paths = create(stage, base, sibling_dirs=sibling_dirs if sibling_dirs else None)

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


def _write_loop_marker(project_root: Path, wt_name: str, wt_paths: list[Path]) -> None:
    """Persist active-worktree paths for this session to a per-session marker file.

    File: ``.claude/.hm-loop-{wt_name}`` — one file per active session so
    parallel sessions coexist without overwriting each other (ADR-006).
    Content: newline-separated absolute paths. Single-repo = one line,
    multi-repo = N lines.

    Atomic write — concurrent readers (gate hook) must never see partial.
    Also ensures ``.claude/.hm-loop-*`` is in ``.gitignore``.
    """
    from harness_maker.io_utils import atomic_write

    marker = _marker_path(project_root, wt_name)
    content = "\n".join(str(p) for p in wt_paths) + "\n"
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
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
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
    marker = _marker_path(project_root, primary_wt_name)
    if not marker.is_file():
        return [fallback]
    try:
        text = marker.read_text(encoding="utf-8")
    except OSError:
        return [fallback]
    paths = [Path(ln.strip()) for ln in text.splitlines() if ln.strip()]
    return paths if paths else [fallback]


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
    wt = Path(wt_str)
    # Project root = parent of `.worktrees/<name>` (mirrors cleanup's logic).
    project_root = wt.resolve().parent.parent
    primary_wt_name = wt.resolve().name
    auto_commit = status == "success"

    all_wts = _session_worktrees(project_root, primary_wt_name, wt)

    # Nothing to do if all WTs have already been cleaned up (idempotent no-op).
    if not any(p.is_dir() for p in all_wts):
        return 0

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

        # ADR-001: stash base's pre-existing dirty BEFORE squash so the merge
        # runs on a clean tree. Both modes engage isolation; success mode pops
        # inside the envelope, stage-only hands off via the ref file.
        stash_ref: str | None = None
        try:
            stash_ref = _stash_base_dirty(base_repo, current_wt.name)
        except RuntimeError as e:
            print(f"[finalize] stash setup failed: {e}", file=sys.stderr)
            return 1

        # handed_off: True means recovery is owned by a downstream actor
        # (the wrapup-side post-commit-pop). When True, the finally clause
        # must NOT pop — doing so would re-contaminate the index with the
        # user's dirty on top of the staged squash (validator 2nd-pass critical).
        handed_off = stash_ref is None  # no stash → vacuously complete

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
                # PLAN-worktree-cross-session-data-loss-defense:
                # ADR-005 merge fence — serialize parallel finalize.
                # ADR-006 scope-guard (warn-only) — detect merge sweeping
                # unrelated staged files into the squash. Pre-existing
                # staged content (--allow-dirty-base path) is excluded
                # via staged_before snapshot.
                try:
                    staged_before_proc = _run(
                        ["git", "diff", "--cached", "--name-only"], cwd=base_repo
                    )
                    staged_before = set(staged_before_proc.stdout.strip().splitlines())
                except RuntimeError:
                    staged_before = set()

                try:
                    with _acquire_merge_fence(base_repo, timeout=60.0):
                        merge(current_wt, strategy=strategy, commit=auto_commit)
                except (RuntimeError, TimeoutError) as e:
                    print(f"merge failed, preserving worktree: {e}", file=sys.stderr)
                    wt_rc = 1

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
                ok, klass, files = _restore_base_dirty(base_repo, stash_ref)
                handed_off = True  # success-mode pop done; suppress finally pop
                if not ok:
                    _emit_pop_failure_signal(klass, stash_ref, files, current_wt.name)
                    pop_rc = 1
        finally:
            # Rollback path: only pop when something raised BEFORE handoff. For
            # stage-only rollback, reset the partially-staged squash first so
            # pop doesn't conflict with our half-applied merge state.
            if stash_ref is not None and not handed_off:
                if not auto_commit:
                    with contextlib.suppress(RuntimeError):
                        _run(["git", "reset", "--hard", "HEAD"], cwd=base_repo)
                ok, klass, files = _restore_base_dirty(base_repo, stash_ref)
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
            if owned_uuids and ref_session_uuid and ref_session_uuid not in owned_uuids:
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
    """
    if len(args) != 1:
        print("usage: owned-uuids <base_dir>", file=sys.stderr)
        return 2
    base = Path(args[0]).resolve()
    uuids = sorted(_owned_session_uuids(base))
    print(",".join(uuids))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch worktree subcommand from argv."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "usage: python -m harness_maker.worktree "
            "<create|finalize|post-commit-pop|owned-uuids> [...]",
            file=sys.stderr,
        )
        return 2
    sub, rest = args[0], args[1:]
    if sub == "create":
        return _cli_create(rest)
    if sub == "finalize":
        return _cli_finalize(rest)
    if sub == "post-commit-pop":
        return _cli_post_commit_pop(rest)
    if sub == "owned-uuids":
        return _cli_owned_uuids(rest)
    print(f"unknown subcommand: {sub}", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess
    sys.exit(main())
