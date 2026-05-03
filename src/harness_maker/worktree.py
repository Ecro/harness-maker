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
from datetime import UTC, datetime
from pathlib import Path

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
    """
    base = base_dir.resolve()
    name = f"{workflow}-{_timestamp()}"
    wt_path = base / WORKTREE_DIR_NAME / name
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    # Create a new branch tracking the current HEAD inside the worktree.
    _run(["git", "worktree", "add", "-b", name, str(wt_path)], cwd=base)
    return wt_path


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
