"""Phase 2 (ADR-002, ADR-006, ADR-010): persistent per-task worktree + path-ownership.

task_create makes a DETERMINISTIC persistent worktree `.worktrees/<slug>/` on branch
`hm/<slug>` (not the ephemeral execute-<uuid>), registers the session, is idempotent, and
copies gitignored secrets in while excluding them via the per-worktree info/exclude (so
they never land in the squash). `_path_owner` is the code form of the ADR-010 matrix.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker import worktree


def _git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )
    return cp.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n.claude/\n.env\n")
    (repo / "README.md").write_text("x\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


# ── ADR-010 path-ownership classifier ────────────────────────────────────────


@pytest.mark.parametrize(
    ("relpath", "owner"),
    [
        ("work-docs/PLAN-foo.md", "deliverable"),
        ("work-docs/RESEARCH-foo.md", "deliverable"),
        ("specs/SPEC-foo.md", "deliverable"),
        (".claude/memory/wiki.md", "deliverable"),
        (".claude/memory/session/2026-06-20.md", "deliverable"),
        (".hm-loop-active", "operational"),
        (".claude/.hm-sessions.json", "operational"),
        (".claude/observability/metrics.jsonl", "operational"),
        (".claude/.hm-iter-receipts/iter-1/plan.json", "operational"),
        (".claude/agents/custom.md", "user"),
        (".claude/harness.yaml", "user"),
        ("src/harness_maker/worktree.py", "user"),
        ("/outside/the/repo/vault-note.md", "external"),
        ("../escapes/repo.md", "external"),
    ],
)
def test_path_owner_classifies(relpath: str, owner: str) -> None:
    assert worktree._path_owner(relpath) == owner


# ── task helpers ─────────────────────────────────────────────────────────────


def test_task_branch_and_path() -> None:
    assert worktree.task_branch("my-feature") == "hm/my-feature"
    base = Path("/tmp/repo")
    assert worktree.task_worktree_path(base, "my-feature") == base / ".worktrees" / "my-feature"


# ── task_create lifecycle ────────────────────────────────────────────────────


def test_task_create_makes_branch_worktree_and_registry_row(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = worktree.task_create(repo, "feat", session_uuid="u-feat-0001")

    assert wt == repo / ".worktrees" / "feat"
    assert wt.is_dir()
    assert _git(["rev-parse", "--abbrev-ref", "HEAD"], wt) == "hm/feat"
    assert "hm/feat" in _git(["branch", "--format=%(refname:short)"], repo).split()
    rows = worktree._read_sessions(repo)
    assert [(r.branch, r.session_uuid) for r in rows] == [("hm/feat", "u-feat-0001")]


def test_task_create_is_idempotent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt1 = worktree.task_create(repo, "feat", session_uuid="u-feat-0001")
    wt2 = worktree.task_create(repo, "feat", session_uuid="u-feat-0001")

    assert wt1 == wt2
    # one branch, one registry row (no duplicates)
    branches = _git(["branch", "--format=%(refname:short)"], repo).split()
    assert branches.count("hm/feat") == 1
    assert len(worktree._read_sessions(repo)) == 1


def test_task_create_excludes_secret_via_per_worktree_info_exclude(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".env").write_text("SECRET=1\n")  # gitignored at base
    wt = worktree.task_create(repo, "feat", session_uuid="u-feat-0001", include=[".env"])

    # secret copied INTO the worktree
    assert (wt / ".env").read_text() == "SECRET=1\n"
    # but excluded there via per-worktree info/exclude → not a tracked/untracked dirt
    status = _git(["status", "--porcelain"], wt)
    assert ".env" not in status


# ── REVIEW Phase 2 hardening (auto-fix) ──────────────────────────────────────


def test_task_create_distinct_uuid_keeps_one_row_per_branch(tmp_path: Path) -> None:
    """Reuse with a FRESH session_uuid self-heals the registry to exactly one row."""
    repo = _repo(tmp_path)
    worktree.task_create(repo, "feat", session_uuid="uuid-first-0001")
    worktree.task_create(repo, "feat", session_uuid="uuid-second-002")  # new session
    rows = worktree._read_sessions(repo)
    assert [r.branch for r in rows] == ["hm/feat"]
    assert rows[0].session_uuid == "uuid-second-002"  # latest session claims it


def test_task_create_reregisters_after_row_reclaimed(tmp_path: Path) -> None:
    """Absent-case black hole: worktree present but row gone → reuse re-registers."""
    repo = _repo(tmp_path)
    worktree.task_create(repo, "feat", session_uuid="u-1")
    worktree.release_session(repo, session_uuid="u-1")  # simulate reclaim
    assert worktree._read_sessions(repo) == []
    worktree.task_create(repo, "feat", session_uuid="u-2")  # reuse (dir present)
    assert [r.branch for r in worktree._read_sessions(repo)] == ["hm/feat"]


def test_task_create_reattaches_existing_branch_when_dir_gone(tmp_path: Path) -> None:
    """Branch exists but worktree dir removed → reattach, not a permanent wedge."""
    repo = _repo(tmp_path)
    wt = worktree.task_create(repo, "feat", session_uuid="u-1")
    _git(["worktree", "remove", "--force", str(wt)], repo)  # dir gone, branch kept
    assert not wt.is_dir()
    assert "hm/feat" in _git(["branch", "--format=%(refname:short)"], repo).split()
    wt2 = worktree.task_create(repo, "feat", session_uuid="u-2")  # must reattach
    assert wt2 == wt
    assert wt2.is_dir()


@pytest.mark.parametrize("bad", ["../escape", "a/b", "..", "-flag", ".hidden", "a b"])
def test_task_create_rejects_bad_slug(tmp_path: Path, bad: str) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(ValueError, match="invalid task slug"):
        worktree.task_create(repo, bad, session_uuid="u-1")


def test_copy_secrets_skips_tracked_file(tmp_path: Path) -> None:
    """A TRACKED file as include must NOT be copied (info/exclude is a no-op for it →
    it would otherwise land a modification in the squash)."""
    repo = _repo(tmp_path)  # README.md is tracked
    wt = worktree.task_create(repo, "feat", session_uuid="u-1", include=["README.md"])
    # the worktree's README is its own checkout; status stays clean (not overwritten)
    assert _git(["status", "--porcelain"], wt) == ""


def test_copy_secrets_rejects_traversal_include(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("LEAK\n")
    wt = worktree.task_create(
        repo, "feat", session_uuid="u-1", include=["../outside-secret.txt", "/etc/hostname"]
    )
    # neither traversal entry copied into the worktree
    assert (
        not (wt / ".." / "outside-secret.txt").exists() or not (tmp_path / "repo-copied").exists()
    )
    assert not (wt / "outside-secret.txt").exists()


def test_copy_secrets_excludes_metachar_filename(tmp_path: Path) -> None:
    """A metachar secret filename must be excluded LITERALLY, not parsed as a glob."""
    repo = _repo(tmp_path)
    # escaped pattern so the LITERAL file is gitignored in base (passes the
    # check-ignore guard); the metachars then exercise _gitignore_literal escaping.
    (repo / ".gitignore").write_text(".worktrees/\n.claude/\nsecret\\[p\\].env\n")
    _git(["add", ".gitignore"], repo)
    _git(["commit", "-m", "ignore"], repo)
    (repo / "secret[p].env").write_text("K=1\n")
    wt = worktree.task_create(repo, "feat", session_uuid="u-1", include=["secret[p].env"])
    assert (wt / "secret[p].env").read_text() == "K=1\n"
    assert "secret[p].env" not in _git(["status", "--porcelain"], wt)


def test_path_owner_machine_memory_tiers_are_operational() -> None:
    assert worktree._path_owner(".claude/memory/semantic/x.json") == "operational"
    assert worktree._path_owner(".claude/memory/episodic/x.json") == "operational"
    assert worktree._path_owner(".claude/memory/profile/x.json") == "operational"
