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
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_maker.io_utils import load_harness_yaml

WORKTREE_DIR_NAME = ".worktrees"
_TS_FMT = "%Y%m%dT%H%MZ"
_GIT_TIMEOUT = 60  # seconds — prevent hang on SSH prompt or NFS stall

# Per-session marker files: .claude/.hm-loop-{primary-wt-basename}
# One file per active session — parallel sessions coexist without collision.
# Gate reads all matching files via glob. Finalize deletes only its own file.
_LOOP_MARKER_DIR = Path(".claude")
_LOOP_MARKER_PREFIX = ".hm-loop-"
_LOOP_MARKER_GITIGNORE_PATTERN = ".claude/.hm-loop-*"


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Wrap subprocess.run with check=True + capture; uniform error surface."""
    try:
        return subprocess.run(  # noqa: S603 — args list, no shell
            args,
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except subprocess.CalledProcessError as e:
        msg = (
            f"git command failed (exit {e.returncode}): {' '.join(args)}\n"
            f"stderr: {e.stderr.strip() if e.stderr else '<empty>'}"
        )
        raise RuntimeError(msg) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"git command timed out after {_GIT_TIMEOUT}s: {' '.join(args)}") from e


def _timestamp() -> str:
    """UTC ISO8601 minute-precision suffix (filesystem-safe)."""
    return datetime.now(UTC).strftime(_TS_FMT)


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

    ts = _timestamp()
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

    Returns the stash ref (`stash@{N}`) when something was stashed, or None
    when base was clean OR only harness-managed artifacts (.worktrees/, our
    markers, our stash refs) are present. The ref is resolved by message-grep
    so a concurrent stash from another tool doesn't shift ``stash@{0}`` out
    from under us.
    """
    status = _run(["git", "status", "--porcelain"], cwd=base)
    user_lines = [
        line for line in status.stdout.splitlines() if not _is_harness_artifact(line)
    ]
    if not user_lines:
        return None
    message = f"{_STASH_MESSAGE_PREFIX}{wt_name}"
    _run(["git", "stash", "push", "-u", "-m", message], cwd=base)
    listing = _run(["git", "stash", "list"], cwd=base)
    # Exact-match the message field (after the last `": "`) to avoid substring
    # collisions with prefix-shared messages from prior failed runs. Format
    # is `stash@{N}: On <branch>: <message>` or `stash@{N}: WIP on ...: <message>`;
    # splitting on `": "` with maxsplit=2 isolates the message field cleanly.
    for line in listing.stdout.splitlines():
        parts = line.split(": ", 2)
        if len(parts) == 3 and parts[2].strip() == message:
            ref = parts[0].strip()
            if ref.startswith("stash@{"):
                return ref
    raise RuntimeError(
        f"stash push reported success but ref not found in `git stash list` for message {message!r}"
    )


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


def _restore_base_dirty(base: Path, stash_ref: str) -> tuple[bool, str, list[Path]]:
    """Pop the stash. Returns (ok, klass, files); on failure stash is preserved.

    Success → (True, "", []).
    Failure → (False, "merge_conflict" | "untracked_collision" | "unknown", files).
    """
    try:
        _run(["git", "stash", "pop", stash_ref], cwd=base)
        return (True, "", [])
    except RuntimeError as e:
        klass, files = _classify_pop_failure(str(e), base)
        return (False, klass, files)


def _emit_pop_failure_signal(
    klass: str, stash_ref: str, files: list[Path], wt_name: str
) -> None:
    """Write the literal stderr block Step 5 LLM matches on (ADR-003)."""
    if klass == "merge_conflict":
        signal = _POP_CONFLICT_SIGNAL
        recovery = (
            f"Resolve: grep -l '<<<<<<<' . then edit + git add + "
            f"git stash drop {stash_ref}"
        )
    elif klass == "untracked_collision":
        signal = _UNTRACKED_COLLISION_SIGNAL
        recovery = (
            f"Recover: git checkout {stash_ref} -- <file> "
            f"(rename first if needed) then git stash drop {stash_ref}"
        )
    else:
        signal = "[finalize] stash-pop failed (class=unknown) — autoloop must halt"
        recovery = (
            f"Inspect: git stash show -p {stash_ref}; "
            f"resolve manually; git stash drop {stash_ref}"
        )
    print(signal, file=sys.stderr)
    print(f"Stash: {stash_ref} ({_STASH_MESSAGE_PREFIX}{wt_name})", file=sys.stderr)
    label = "Files (in stash, not restored)" if klass == "untracked_collision" else "Files"
    print(f"{label}: {[str(f) for f in files]}", file=sys.stderr)
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


def _write_stash_ref_file(base: Path, wt_name: str, stash_ref: str) -> Path:
    """Persist the stash handoff state (ADR-001 §2).

    Body is 4 simple ``key: value`` lines so ``post-commit-pop`` can read with
    a trivial parser without dragging a YAML dep into the worktree subpackage.
    The session field is the per-session marker basename so we can later
    cross-check that the live session matches before popping (validator 2nd-pass
    warning #3).
    """
    from harness_maker.io_utils import atomic_write

    path = _stash_ref_path(base, wt_name)
    body = (
        f"ref: {stash_ref}\n"
        f"base: {base.resolve()}\n"
        f"session: {_LOOP_MARKER_PREFIX}{wt_name}\n"
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


def _session_marker_present(base: Path, session_basename: str) -> bool:
    """True iff ``<base>/.claude/<session_basename>`` exists as a file.

    A live session marker means the wrapup invocation belongs to the same
    session that created the stash; an absent marker means the prior session
    died without wrapup and the ref file is stale (do not pop, validator
    2nd-pass warning #3).
    """
    return (base / _LOOP_MARKER_DIR / session_basename).is_file()


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
    """Read sibling_repos from harness.yaml; resolve relative paths against base."""
    try:
        data = load_harness_yaml(harness_yaml)
    except (OSError, yaml.YAMLError):
        return []
    raw = data.get("sibling_repos")
    if not isinstance(raw, list):
        return []
    return [(base / rel).resolve() for rel in raw if isinstance(rel, str)]


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
    if len(args) != 2:
        print("usage: create <stage> <base_dir>", file=sys.stderr)
        return 2
    stage, base_str = args
    base = Path(base_str).resolve()

    existing = _detect_existing_worktree(base)
    if existing is not None:
        # Already inside a worktree; marker should already be in place from
        # the parent loop's create. No-op idempotent return.
        print(str(existing))
        return 0

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
    - File present, entry absent → append with leading newline if needed

    Failures are silently swallowed: gitignore hygiene is best-effort, not
    a hard correctness requirement. The gate still works; users may have
    a marker to manually clean up if a loop crashes.
    """
    gitignore = project_root / ".gitignore"
    try:
        if gitignore.is_file():
            existing = gitignore.read_text(encoding="utf-8")
            # Match by line — `.claude/.hm-loop-active` (avoid false-match of
            # a longer line that happens to start with our pattern).
            for line in existing.splitlines():
                if line.strip() == entry:
                    return
            sep = "" if existing.endswith("\n") else "\n"
            with gitignore.open("a", encoding="utf-8") as f:
                f.write(f"{sep}{entry}\n")
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
        if (candidate / ".git").exists():
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
    pending = list(all_wts)

    for current_wt in all_wts:
        if not current_wt.is_dir():
            # Already processed in a prior run (idempotent re-run).
            succeeded.append(current_wt)
            pending.remove(current_wt)
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
                try:
                    merge(current_wt, strategy=strategy, commit=auto_commit)
                except RuntimeError as e:
                    print(f"merge failed, preserving worktree: {e}", file=sys.stderr)
                    wt_rc = 1

            # ADR-001 §2 stage-only handshake: write the ref file AFTER merge
            # succeeds but BEFORE cleanup, then flip handed_off. Cleanup failure
            # after this point cannot re-contaminate because the finally pop is
            # suppressed by handed_off=True; recovery is owned by post-commit-pop.
            if wt_rc == 0 and not auto_commit and stash_ref is not None:
                try:
                    _write_stash_ref_file(base_repo, current_wt.name, stash_ref)
                    handed_off = True
                except OSError as e:
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
        pending.remove(current_wt)

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

    Globs ``<base_dir>/.claude/.hm-finalize-stash-*`` ref files, pops only
    those whose ``session:`` marker is still on disk (live session check —
    validator 2nd-pass warning #3 — prevents stale-ref contamination across
    sessions). On successful pop, deletes the ref file and the session marker.

    Exit codes:
      0 — every actionable ref popped cleanly (or no refs found, or all stale).
      1 — at least one pop failed; the failing ref + stash are preserved with
          a classified signal so the wrapup-side LLM can AskUserQuestion.
    """
    if len(args) != 1:
        print("usage: post-commit-pop <base_dir>", file=sys.stderr)
        return 2
    base = Path(args[0]).resolve()
    claude_dir = base / _LOOP_MARKER_DIR
    if not claude_dir.is_dir():
        return 0  # nothing to do

    overall_rc = 0
    for ref_file in sorted(claude_dir.glob(f"{_STASH_REF_PREFIX}*")):
        fields = _read_stash_ref_file(ref_file)
        stash_ref = fields.get("ref", "")
        session = fields.get("session", "")
        if not stash_ref or not session:
            print(
                f"[post-commit-pop] skipping malformed ref file: {ref_file}",
                file=sys.stderr,
            )
            continue

        if not _session_marker_present(base, session):
            # Stale ref from a prior session that never wrapped up. Skip without
            # touching either the stash or the ref file — the next live session
            # owning that worktree name will recover; or user resolves manually.
            print(
                f"[post-commit-pop] stale ref (session {session!r} not active): "
                f"{ref_file.name} — skipping, stash + ref preserved",
                file=sys.stderr,
            )
            continue

        # Live session match — pop and clean up.
        # Derive worktree name from filename (everything after the prefix).
        wt_name = ref_file.name[len(_STASH_REF_PREFIX) :]
        ok, klass, files = _restore_base_dirty(base, stash_ref)
        if not ok:
            _emit_pop_failure_signal(klass, stash_ref, files, wt_name)
            overall_rc = 1
            continue

        # Successful pop: delete the ref file and the session marker so the
        # next wrapup invocation doesn't try to pop a drained stash.
        ref_file.unlink(missing_ok=True)
        (claude_dir / session).unlink(missing_ok=True)

    return overall_rc


def main(argv: list[str] | None = None) -> int:
    """Dispatch worktree subcommand from argv."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "usage: python -m harness_maker.worktree <create|finalize|post-commit-pop> [...]",
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
    print(f"unknown subcommand: {sub}", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess
    sys.exit(main())
