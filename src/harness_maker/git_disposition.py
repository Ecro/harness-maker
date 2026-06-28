"""Post-render git disposition: detect commit/ignore state + idempotently gitignore target roots.

WHY: ``/harness-maker:make`` leaves generated harness files on disk but never guides the user
on whether to commit them (team-share) or gitignore them (solo). This module owns the
*testable* mechanics — git-state detection and gitignore mutation — while the slash command
owns the interactive prompt and the commit itself (CLAUDE.md: the CLI never commits).
"""

from __future__ import annotations

import fnmatch
import json
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from harness_maker.io_utils import load_harness_yaml
from harness_maker.worktree import _HARNESS_GITIGNORE_PATTERNS, _ensure_gitignore_entry

_GIT_TIMEOUT = 10
_MANIFEST_REL = ".claude/.harness-manifest.json"
_HARNESS_YAML_REL = ".claude/harness.yaml"


class GitDispositionError(Exception):
    """Raised when an explicit user git action cannot be carried out (loud failure)."""


@dataclass(frozen=True)
class GitStatus:
    """Inferred git disposition of the rendered harness roots."""

    is_git: bool
    target_roots: list[str]
    prior_decision: str  # "undecided" | "commit" | "ignore"
    decision_needed: bool
    offer_stage: bool
    untracked_files: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_target_roots(targets: Iterable[str]) -> list[str]:
    """Generated-content roots for the selected IDE targets (``.claude/`` always present)."""
    tset = {str(t) for t in targets}
    roots = [".claude/"]
    if "cursor" in tset:
        roots.append(".cursor/")
    if "codex" in tset:
        roots.extend([".codex/", ".agents/", "AGENTS.md"])
    return roots


def _read_targets(project_root: Path) -> list[str]:
    try:
        body = load_harness_yaml(project_root / _HARNESS_YAML_REL)
    except (FileNotFoundError, OSError, yaml.YAMLError):
        return ["claude-code"]
    val = body.get("targets")
    if isinstance(val, list) and val:
        return [str(t) for t in val]
    return ["claude-code"]


def _git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git with ``check=False`` — callers branch on returncode.

    WHY check=False: ``git check-ignore`` returns exit 1 when a path is NOT ignored
    (the common ``decision_needed`` case); ``check=True`` (worktree._run) would crash there.
    """
    return subprocess.run(  # noqa: S603
        ["git", *args],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=False,
    )


def _is_git_worktree(project_root: Path) -> bool:
    try:
        r = _git(project_root, "rev-parse", "--is-inside-work-tree")
    except (subprocess.SubprocessError, OSError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


def _is_churn(path: str) -> bool:
    """True iff ``path`` is a harness-churn artifact (already individually gitignored)."""
    for pat in _HARNESS_GITIGNORE_PATTERNS:
        if pat.endswith("/"):
            if path.startswith(pat):
                return True
        elif "*" in pat:
            if fnmatch.fnmatch(path, pat):
                return True
        elif path == pat:
            return True
    return False


def _is_traversal(path: str) -> bool:
    """True iff path escapes the project via a `..` segment (defense-in-depth).

    The manifest is harness-self-authored and all git sinks here are read-only, so this
    is hardening, not a live vuln — but a `..`-bearing unit should never reach a git probe.
    """
    return ".." in PurePosixPath(path).parts


def _under_roots(path: str, roots: list[str]) -> bool:
    for r in roots:
        if r.endswith("/"):
            if path.startswith(r):
                return True
        elif path == r:
            return True
    return False


def _read_manifest_files(project_root: Path) -> list[str]:
    try:
        data = json.loads((project_root / _MANIFEST_REL).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    files = data.get("files")
    if not isinstance(files, list):
        return []
    return [str(f) for f in files]


def _tracked_paths(project_root: Path, roots: list[str]) -> set[str]:
    r = _git(project_root, "ls-files", "--", *roots)
    if r.returncode != 0:
        return set()
    return {line for line in r.stdout.splitlines() if line}


def _unit_tracked(unit: str, tracked: set[str]) -> bool:
    if unit in tracked:
        return True
    if unit.endswith("/"):
        return any(t.startswith(unit) for t in tracked)
    return False


def _is_ignored(project_root: Path, path: str) -> bool:
    # rc 0 = ignored, 1 = not ignored, 128 = error (treat as not ignored).
    return _git(project_root, "check-ignore", "-q", "--", path).returncode == 0


def compute_git_status(project_root: Path) -> GitStatus:
    """Infer whether the rendered harness roots are committed, ignored, or undecided.

    Decision is inferred from current git state each run (never persisted) so a re-render
    does not re-nag (CLAUDE.md #5/#6). Units are the rendered non-churn manifest files
    restricted to the active target roots; absent a manifest, the present root dirs.
    """
    roots = resolve_target_roots(_read_targets(project_root))
    if not _is_git_worktree(project_root):
        return GitStatus(False, roots, "undecided", False, False, [])

    units = [
        f
        for f in _read_manifest_files(project_root)
        if _under_roots(f, roots) and not _is_churn(f) and not _is_traversal(f)
    ]
    if not units:
        units = [r for r in roots if (project_root / r.rstrip("/")).exists()]
    if not units:
        return GitStatus(True, roots, "undecided", False, False, [])

    tracked = _tracked_paths(project_root, roots)
    tracked_set = {u for u in units if _unit_tracked(u, tracked)}
    ignored_set = {u for u in units if _is_ignored(project_root, u)}
    undecided = sorted(u for u in units if u not in tracked_set and u not in ignored_set)

    if tracked_set:
        prior = "commit"
    elif not undecided:  # every unit ignored, none tracked
        prior = "ignore"
    else:
        prior = "undecided"

    decision_needed = prior == "undecided"
    offer_stage = prior == "commit" and bool(undecided)
    return GitStatus(True, roots, prior, decision_needed, offer_stage, undecided)


def ignore_roots(project_root: Path) -> list[str]:
    """Idempotently gitignore the present harness roots; fail loudly on any problem.

    Unlike the best-effort churn helper, this represents an EXPLICIT user decision, so a
    silent no-op is unacceptable: a non-work-tree raises, and after appending we re-verify
    each root is actually ``check-ignore``-matched (a negation rule or unwritable
    ``.gitignore`` would otherwise let the slash report a false success → endless re-nag).
    """
    if not _is_git_worktree(project_root):
        raise GitDispositionError(
            f"{project_root} is not a git work tree — cannot gitignore harness roots"
        )
    roots = resolve_target_roots(_read_targets(project_root))
    present = [r for r in roots if (project_root / r.rstrip("/")).exists()]
    for r in present:
        _ensure_gitignore_entry(project_root, r)
    failed = [r for r in present if not _is_ignored(project_root, r)]
    if failed:
        raise GitDispositionError(
            "gitignore append did not take effect for: "
            + ", ".join(failed)
            + " (.gitignore may be unwritable or shadowed by a negation rule)"
        )
    return present
