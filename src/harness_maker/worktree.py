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
    """
    if len(args) != 2:
        print("usage: create <stage> <base_dir>", file=sys.stderr)
        return 2
    stage, base_str = args
    base = Path(base_str).resolve()
    yaml_path = base / ".claude" / "harness.yaml"
    if not _scope_includes(yaml_path, stage):
        print("")
        return 0
    wt_path = create(stage, base)
    print(str(wt_path))
    return 0


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
