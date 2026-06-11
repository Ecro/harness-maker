"""PLAN-worktree-deliverable-blocks-create ADR-003/004 — landed-marker branch sweep.

`_branch_content_in_head` re-compares current blob SHAs and never re-matches
after a landed branch's files are re-edited → branches preserve forever (the
74-branch wall). ADR-003: finalize records the branch tip as
`refs/hm-landed/v1/<branch>`; prune_stale deletes a markered branch iff its tip
still equals the recorded SHA (survives later HEAD edits; name-collision safe).
ADR-004: orphan markers reaped on every path; `prune-branches [--force]` drains
the legacy backlog.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from harness_maker import worktree
from harness_maker.worktree import (
    _list_landed_markers,
    _read_landed_marker,
    _write_landed_marker,
    prune_stale,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(".claude/\n.worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("base")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def _make_branch_with_divergent_commit(repo: Path, branch: str, fname: str) -> str:
    """Create an owned-prefix branch whose tip has content NOT in main's HEAD.

    Returns the branch tip SHA. No worktree dir is created, so prune_stale
    treats it as an orphan candidate.
    """
    _git(repo, "branch", branch)
    _git(repo, "checkout", branch)
    (repo / fname).write_text("divergent content")
    _git(repo, "add", fname)
    _git(repo, "commit", "-m", f"wip on {branch}")
    tip = _git(repo, "rev-parse", branch)
    _git(repo, "checkout", "main")
    return tip


def _branch_exists(repo: Path, branch: str) -> bool:
    cp = subprocess.run(
        ["git", "branch", "--list", branch], cwd=repo, capture_output=True, text=True
    )
    return bool(cp.stdout.strip())


# ── marker round-trip ───────────────────────────────────────────────────────


def test_write_then_read_landed_marker_round_trips_tip(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    branch = "execute-aaaaaaaaaaaa-20260101T0000Z"
    tip = _make_branch_with_divergent_commit(repo, branch, "a.txt")
    _write_landed_marker(repo, branch)
    assert _read_landed_marker(repo, branch) == tip


def test_read_landed_marker_absent_returns_none(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    assert _read_landed_marker(repo, "execute-nope-20260101T0000Z") is None


# ── ADR-003 sweep: marker matches tip → delete regardless of content ────────


def test_marker_matching_tip_sweeps_even_when_content_not_in_head(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    branch = "execute-bbbbbbbbbbbb-20260101T0000Z"
    _make_branch_with_divergent_commit(repo, branch, "b.txt")
    _write_landed_marker(repo, branch)  # tip == marker; content NOT in HEAD
    report = prune_stale(repo)
    assert branch in report.removed_branches
    assert not _branch_exists(repo, branch)
    # Marker deleted in the same op (ADR-004).
    assert _read_landed_marker(repo, branch) is None


# ── ADR-003 stale marker: tip advanced → NOT marker-deleted → content-gate ──


def test_stale_marker_does_not_delete_a_diverged_branch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    branch = "execute-cccccccccccc-20260101T0000Z"
    _make_branch_with_divergent_commit(repo, branch, "c.txt")
    _write_landed_marker(repo, branch)
    # Tip advances after the marker was written (name-collision / re-use proxy).
    _git(repo, "checkout", branch)
    (repo / "c2.txt").write_text("more")
    _git(repo, "add", "c2.txt")
    _git(repo, "commit", "-m", "advance tip")
    _git(repo, "checkout", "main")
    report = prune_stale(repo)
    # tip != marker_SHA → marker ignored → content-gate preserves (not in HEAD).
    assert branch not in report.removed_branches
    assert _branch_exists(repo, branch)


# ── ADR-004 orphan reaping ──────────────────────────────────────────────────


def test_orphan_marker_with_no_branch_is_reaped(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    ghost = "execute-ghostghostgh-20260101T0000Z"
    # Write a marker ref pointing at HEAD for a branch that does not exist.
    head = _git(repo, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "update-ref", f"refs/hm-landed/v1/{ghost}", head],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    assert ghost in _list_landed_markers(repo)
    report = prune_stale(repo)
    assert ghost in report.removed_landed_markers
    assert ghost not in _list_landed_markers(repo)


# ── ADR-004 legacy markerless: content-in-HEAD fallback still sweeps ─────────


def test_legacy_markerless_branch_with_content_in_head_is_swept(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    branch = "execute-dddddddddddd-20260101T0000Z"
    # Branch at HEAD: its (empty) diff content is trivially in HEAD → swept.
    _git(repo, "branch", branch)
    report = prune_stale(repo)
    assert branch in report.removed_branches
    assert not _branch_exists(repo, branch)


# ── ADR-004 prune-branches CLI (subprocess — exit (f)/(i)) ───────────────────


def _run(repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "prune-branches", str(repo), *extra],
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_prune_branches_cli_reachable_and_exits_zero(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    proc = _run(repo)
    assert proc.returncode == 0, f"prune-branches not reachable: {proc.stderr}"


def test_prune_branches_cli_non_force_preserves_diverged(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    branch = "execute-eeeeeeeeeeee-20260101T0000Z"
    _make_branch_with_divergent_commit(repo, branch, "e.txt")
    proc = _run(repo)
    assert proc.returncode == 0, proc.stderr
    assert _branch_exists(repo, branch), "non-force must not delete a diverged branch"


def test_prune_branches_cli_force_deletes_and_prints_recovery_hint(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    branch = "execute-ffffffffffff-20260101T0000Z"
    _make_branch_with_divergent_commit(repo, branch, "f.txt")
    proc = _run(repo, "--force")
    assert proc.returncode == 0, proc.stderr
    assert not _branch_exists(repo, branch), "--force must delete the diverged branch"
    assert f"git log -p {branch}" in proc.stdout, "recovery hint must be printed before delete"


# ── ADR-004 (g) warning summarization: N preserved → ONE warning line ───────


def test_create_summarizes_many_preserved_branches_to_one_warning_line(tmp_path: Path) -> None:
    """Exit-criterion (g): the per-branch `preserved branch …` wall (the 74-line
    noise this work removes) collapses to a single summary line on `create`."""
    repo = _init_repo(tmp_path)
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "harness.yaml").write_text(
        "worktree:\n  scope: [execute]\n", encoding="utf-8"
    )
    for i in range(3):
        _make_branch_with_divergent_commit(repo, f"execute-{i:012d}-20260101T0000Z", f"p{i}.txt")
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "create", "execute", str(repo)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stderr
    preserved_lines = [
        ln for ln in proc.stderr.splitlines() if "[WARN]" in ln and "preserved" in ln.lower()
    ]
    assert len(preserved_lines) == 1, (
        f"expected 1 summary line, got {len(preserved_lines)}:\n{proc.stderr}"
    )


# ── ADR-003 producer: finalize (the SOLE marker writer) is pinned end-to-end ─


def test_finalize_writes_landed_marker_at_branch_tip(tmp_path: Path) -> None:
    """Pin the production producer: a real create→finalize cycle must write
    `refs/hm-landed/v1/<branch>` = the branch tip. Without this, a regression in
    the finalize-side `_write_landed_marker` call site silently reverts the
    feature to the content-gate-preserve wall (absent-case = feature black hole).
    """
    repo = _init_repo(tmp_path)
    (wt,) = worktree.create("execute", repo)
    (wt / "feature.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "feature.py"], cwd=wt, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feature"], cwd=wt, check=True, capture_output=True)
    wt_name = wt.name
    expected_tip = _git(repo, "rev-parse", wt_name)
    rc = worktree._cli_finalize([str(wt), "stage-only"])
    assert rc == 0, "finalize stage-only should succeed on a clean base"
    marker = _read_landed_marker(repo, wt_name)
    assert marker is not None, "finalize must write the landed marker (sole producer)"
    assert marker == expected_tip, "marker must record the branch tip at finalize"
