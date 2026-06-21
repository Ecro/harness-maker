"""Phase 0 (ADR-009): drain trigger relocated off create-only to wrapup/health.

The drain reuses `prune_stale` (the single gate); create-time reaping is RETAINED
additively. The sweep stays content-gated + biased-to-preserve.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from harness_maker import worktree

LANDED = "execute-aaaaaaaaaaaa-20260525T0000Z"
UNMERGED = "execute-bbbbbbbbbbbb-20260525T0000Z"
PROTECTED = "execute-cccccccccccc-20260525T0000Z"


def _git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(  # noqa: S603
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return cp.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n.claude/.hm-loop-*\n")
    (repo / "tracked.txt").write_text("base\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _owned_branch(repo: Path, name: str, *, diverge: bool) -> None:
    """Owned-prefix branch with no worktree dir. diverge=True → content NOT in HEAD."""
    if diverge:
        _git(["checkout", "-b", name], repo)
        (repo / "feature.txt").write_text("unmerged work\n")
        _git(["add", "feature.txt"], repo)
        _git(["commit", "-m", "wip on branch"], repo)
        _git(["checkout", "main"], repo)
    else:
        # tip == main HEAD → branch changed no blobs vs merge-base → content in HEAD.
        _git(["branch", name, "main"], repo)


def _branch_names(repo: Path) -> list[str]:
    return _git(["branch", "--format=%(refname:short)"], repo).split()


def test_drain_deletes_landed_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _owned_branch(repo, LANDED, diverge=False)
    assert LANDED in _branch_names(repo)

    rc = worktree._cli_drain([str(repo)])

    assert rc == 0
    assert LANDED not in _branch_names(repo)  # landed → swept


def test_drain_preserves_unmerged_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _owned_branch(repo, UNMERGED, diverge=True)

    rc = worktree._cli_drain([str(repo)])

    assert rc == 0
    assert UNMERGED in _branch_names(repo)  # biased-to-preserve: never auto-deleted


def test_drain_preserves_protected_path_edit(tmp_path: Path) -> None:
    """Adversarial: a branch diverging on a protected .claude/ path is preserved."""
    repo = _repo(tmp_path)
    _git(["checkout", "-b", PROTECTED], repo)
    agents = repo / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "custom.md").write_text("user-authored agent\n")
    _git(["add", ".claude/agents/custom.md"], repo)
    _git(["commit", "-m", "user protected-path edit"], repo)
    _git(["checkout", "main"], repo)

    report = worktree.prune_stale(repo)

    assert PROTECTED in [b for b, _ in report.preserved_branches]
    assert PROTECTED not in report.removed_branches
    assert PROTECTED in _branch_names(repo)


def test_drain_summary_is_noninteractive() -> None:
    """The auto-trigger summary is one line and never nags to re-run with --force."""
    report = worktree.PruneReport()
    report.removed_branches.append("execute-x")
    report.removed_landed_markers.append("execute-x")
    report.preserved_branches.append(("execute-y", "preserved branch execute-y: content..."))

    summary = worktree._drain_summary(report)

    assert summary.strip().count("\n") == 0  # single line
    assert "--force" not in summary  # no interactive nag
    assert "1" in summary  # surfaces the removed/preserved counts


def test_drain_preserves_unknown_ownership_branch(tmp_path: Path) -> None:
    """Adversarial (c): a non-owned-prefix branch is never considered for sweep."""
    repo = _repo(tmp_path)
    foreign = "cursor-feature-xyz"  # not in _OWNED_PREFIXES
    _git(["branch", foreign, "main"], repo)  # tip==HEAD, yet must NOT be swept

    report = worktree._drain(repo)

    assert foreign not in report.removed_branches
    assert foreign in _branch_names(repo)


def test_create_time_reaping_retained(tmp_path: Path) -> None:
    """ADR-009 additive: `worktree create` must STILL reap orphans (not moved)."""
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir()
    # scope=[] → create runs prune_stale but engages no real worktree.
    # Commit harness.yaml so it is not untracked USER dirt tripping the
    # dirty-base guard (the .hm-loop-* marker + .worktrees/ are gitignored).
    (claude / "harness.yaml").write_text("worktree:\n  scope: []\n")
    _git(["add", ".claude/harness.yaml"], repo)
    _git(["commit", "-m", "harness config"], repo)

    missing_wt = repo / ".worktrees" / "execute-deadbeef9999-20260525T0000Z"
    orphan_marker = claude / f".hm-loop-{missing_wt.name}"
    orphan_marker.write_text(f"{missing_wt}\n")
    dangling = repo / ".worktrees" / "execute-orphaned999-20260525T0000Z"
    dangling.mkdir(parents=True)
    # ADR-001 `.git`-filter (prune-create race): only a real worktree dir (has a
    # `.git` entry) is reapable — a genuine orphan from a crashed session has one.
    (dangling / ".git").write_text("gitdir: /gone\n")

    rc = worktree._cli_create(["execute", str(repo)])

    assert rc == 0
    assert not orphan_marker.exists()  # create-time reaping STILL fires
    assert not dangling.exists()
