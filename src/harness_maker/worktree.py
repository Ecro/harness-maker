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

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

WORKTREE_DIR_NAME = ".worktrees"
_TS_FMT = "%Y%m%dT%H%MZ"

# Marker file written at the project root when a loop engages a worktree.
# `harness_maker.gates.worktree_gate` reads it to enforce <WT>-scoped writes
# (technical fallback for prompt-driven `<WT>` substitution in loop.md.j2).
_LOOP_MARKER_REL = Path(".claude") / ".hm-loop-active"


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Wrap subprocess.run with check=True + capture; uniform error surface."""
    try:
        return subprocess.run(  # noqa: S603 — args list, no shell
            args,
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        msg = (
            f"git command failed (exit {e.returncode}): {' '.join(args)}\n"
            f"stderr: {e.stderr.strip() if e.stderr else '<empty>'}"
        )
        raise RuntimeError(msg) from e


def _timestamp() -> str:
    """UTC ISO8601 minute-precision suffix (filesystem-safe)."""
    return datetime.now(UTC).strftime(_TS_FMT)


def _current_branch(repo: Path) -> str:
    """Return the current branch name of repo (HEAD's symbolic ref)."""
    cp = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    return cp.stdout.strip()


def create(workflow: str, base_dir: Path) -> Path:
    """Create a new git worktree at <base_dir>/.worktrees/<workflow>-<ts>.

    Parameters
    ----------
    workflow:
        The workflow name (e.g. "execute", "dev"); used in the directory name.
    base_dir:
        Path to the base git repository.

    Returns
    -------
    Path to the newly created worktree.

    Notes
    -----
    Timestamps are minute-precision so two ``create()`` calls within the same
    minute (realistic for autoloop / fused workflows) would collide on branch
    name. We retry with ``-1``, ``-2``, ... suffixes up to 100 times before
    giving up; collisions clear once the minute rolls over.
    """
    base = base_dir.resolve()
    base_name = f"{workflow}-{_timestamp()}"
    (base / WORKTREE_DIR_NAME).mkdir(parents=True, exist_ok=True)
    last_err: RuntimeError | None = None
    for attempt in range(100):
        name = base_name if attempt == 0 else f"{base_name}-{attempt}"
        wt_path = base / WORKTREE_DIR_NAME / name
        if wt_path.exists():
            continue
        try:
            _run(["git", "worktree", "add", "-b", name, str(wt_path)], cwd=base)
        except RuntimeError as e:
            # Likely "branch already exists" or "path already exists" — retry
            # with the next suffix. Capture for final failure if all suffixes
            # also collide (extremely unlikely; >100 calls in one minute).
            last_err = e
            continue
        return wt_path
    raise RuntimeError(
        f"git worktree add failed after 100 retries with prefix {base_name!r}; "
        f"last error: {last_err}",
    )


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


def merge(wt_path: Path, strategy: str = "squash") -> None:
    """Merge the worktree's branch back into the base repo's current branch.

    Switches into the base repo and runs `git merge <branch>` with the
    requested strategy. Caller is responsible for choosing when to call this
    (typically: post-success, before cleanup).
    """
    wt = wt_path.resolve()
    base = wt.parent.parent
    branch = wt.name  # branch name == worktree directory basename (see create())
    args = ["git", "merge"]
    if strategy == "squash":
        args.extend(["--squash", branch])
        _run(args, cwd=base)
        # `--squash` stages but does not commit; finalize so the merge is durable.
        _run(
            ["git", "commit", "-m", f"squash-merge worktree {branch}"],
            cwd=base,
        )
    else:
        args.extend([f"--{strategy}", branch] if strategy != "merge" else [branch])
        _run(args, cwd=base)


def _list_worktrees(base_dir: Path) -> list[Path]:
    """Return absolute paths of all worktrees under base_dir/.worktrees/.

    Uses `git worktree list --porcelain` so we don't depend on directory
    enumeration and naturally skip the main worktree.
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
        if WORKTREE_DIR_NAME in p.parts and p.is_relative_to(base):
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
        text = harness_yaml.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        for doc in yaml.safe_load_all(text):
            if not isinstance(doc, dict):
                continue
            wt = doc.get("worktree")
            if not isinstance(wt, dict):
                continue
            scope = wt.get("scope")
            if isinstance(scope, list) and stage in scope:
                return True
    except yaml.YAMLError:
        return False
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
    wt_path = create(stage, base)
    _write_loop_marker(base, wt_path)
    print(str(wt_path))
    return 0


_LOOP_MARKER_GITIGNORE_LINE = ".claude/.hm-loop-active"


def _write_loop_marker(project_root: Path, wt_path: Path) -> None:
    """Persist active-worktree path so worktree_gate can enforce <WT> scope.

    Overwrites any existing marker (treats prior value as orphaned — finalize
    is responsible for cleanup; if a previous loop crashed without finalize,
    this resets state). Atomic write — concurrent readers (the gate hook)
    must never see a partial line.

    Also ensures ``.claude/.hm-loop-active`` is in the project's ``.gitignore``
    so a marker leftover from a crashed loop doesn't get committed and break
    every collaborator's gate against a non-existent worktree path. The
    append is idempotent (no-op when already present) and creates a new
    ``.gitignore`` if absent.
    """
    from harness_maker.io_utils import atomic_write

    marker = project_root / _LOOP_MARKER_REL
    atomic_write(marker, str(wt_path) + "\n")
    _ensure_gitignore_entry(project_root, _LOOP_MARKER_GITIGNORE_LINE)


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
            gitignore.write_text(f"{entry}\n", encoding="utf-8")
    except OSError:
        # Best-effort; don't fail loop creation over a gitignore write.
        pass


def _clear_loop_marker_if_matches(project_root: Path, wt_path: Path) -> None:
    """Remove marker only if it points to ``wt_path``.

    Defensive: if a different loop is now active (concurrent run), don't
    clobber that loop's marker by removing it during this loop's finalize.
    """
    marker = project_root / _LOOP_MARKER_REL
    if not marker.is_file():
        return
    try:
        recorded = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if recorded == str(wt_path):
        marker.unlink(missing_ok=True)


def _detect_existing_worktree(base: Path) -> Path | None:
    """Idempotent dispatch helper — return the enclosing real git worktree.

    Two signals consulted in priority order:

    1. **Loop marker** (`<base>/.claude/.hm-loop-active`) — strongest signal.
       Written by `worktree create` when a loop engages and points at the
       active worktree. Covers the realistic case where /hm:loop runs in
       the project root and dispatches `/hm:execute` whose §0 calls
       `worktree create execute "$(pwd)"` *also* from project root — without
       this, §0 would not see the loop's worktree (cwd is project root, not
       inside `.worktrees/`) and create a SECOND worktree.
    2. **Path-based** (rightmost ``.worktrees`` segment of ``base.parts``)
       — fallback for standalone `/hm:execute` invoked from inside an
       existing worktree, or any case where the marker is absent. To avoid
       false positives — a user's home contains ``~/.worktrees`` from
       another tool, a regular file named ``.worktrees``, a stale dir
       without a real git checkout — we probe for the worktree's ``.git``
       entry (file or dir; ``git worktree add`` writes a file pointing
       at the parent's ``$GIT_DIR/worktrees/<name>``).

    Returns the worktree root Path on confirmed match, else None.
    """
    # 1. Marker-based: the active loop's source of truth.
    marker = base / _LOOP_MARKER_REL
    if marker.is_file():
        try:
            recorded = marker.read_text(encoding="utf-8").strip()
        except OSError:
            recorded = ""
        if recorded:
            wt = Path(recorded)
            if wt.is_dir() and (wt / ".git").exists():
                return wt.resolve()
        # Marker exists but content is stale/unreadable — fall through to
        # path-based check rather than failing loud.

    # 2. Path-based: walk right-to-left so nested .worktrees pick innermost.
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


def _cli_finalize(args: list[str]) -> int:
    """`python -m harness_maker.worktree finalize <wt_path> <success|fail> [strategy]`.

    On success: merge back (default strategy: squash) + cleanup with --force.
    On fail: skip merge; cleanup non-force (preserves dirty worktree for inspection).
    Missing `<wt_path>` is a no-op exit 0 — slash commands wire `finalize`
    unconditionally, and an empty worktree_path means scope check was off.

    Both merge and cleanup failures are caught and surfaced via stderr +
    return 1 so we never crash with a bare traceback (e.g., a locked file
    on Windows blocking ``git worktree remove --force``). The slash command
    treats exit 1 as "finalize had an issue, evidence preserved" rather
    than letting the harness break.
    """
    if len(args) < 2 or len(args) > 3:
        print("usage: finalize <wt_path> <success|fail> [strategy]", file=sys.stderr)
        return 2
    wt_str, status = args[0], args[1]
    strategy = args[2] if len(args) == 3 else "squash"
    if status not in {"success", "fail"}:
        print("status must be 'success' or 'fail'", file=sys.stderr)
        return 2
    wt = Path(wt_str)
    if not wt.is_dir():
        return 0
    # Project root = parent of `.worktrees/<name>` (mirrors cleanup's logic).
    project_root = wt.resolve().parent.parent
    on_success = status == "success"
    if on_success:
        try:
            merge(wt, strategy=strategy)
        except RuntimeError as e:
            print(f"merge failed, preserving worktree: {e}", file=sys.stderr)
            return 1
    try:
        cleanup(wt, on_success=on_success)
    except RuntimeError as e:
        print(f"cleanup failed, worktree preserved at {wt}: {e}", file=sys.stderr)
        return 1
    # Loop is over (success OR failure) → release the marker so
    # worktree_gate stops blocking main edits. Failure preserves the
    # `<WT>` directory for inspection, but the user must be free to edit
    # main again (e.g. cherry-pick from <WT>, discard, retry). Stale
    # markers from crashed loops are also cleaned up here.
    _clear_loop_marker_if_matches(project_root, wt.resolve())
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch worktree subcommand from argv."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python -m harness_maker.worktree <create|finalize> [...]", file=sys.stderr)
        return 2
    sub, rest = args[0], args[1:]
    if sub == "create":
        return _cli_create(rest)
    if sub == "finalize":
        return _cli_finalize(rest)
    print(f"unknown subcommand: {sub}", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess
    sys.exit(main())
