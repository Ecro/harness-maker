"""PLAN-layer3-per-session-ownership Phase 3 — per-session pop isolation (real git).

The contamination regression guard: a session's `post-commit-pop` must PRESERVE a
PEER's deferred stash (foreign session_uuid, even with a live marker), and an EMPTY
owned-set must fail-safe-SKIP a uuid'd ref rather than pop it. `test_worktree_stash.py`
already proves the owner-pops-with-its-own-uuid path via real create+finalize; this
file proves the SKIP (preserve) side, which is where cross-session contamination
would otherwise occur.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker import worktree


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed args, no shell
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(["init", "-b", "main"], cwd=r)
    _git(["config", "user.email", "t@e.com"], cwd=r)
    _git(["config", "user.name", "T"], cwd=r)
    (r / "README.md").write_text("# repo\n")
    (r / ".gitignore").write_text(".claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n")
    _git(["add", "."], cwd=r)
    _git(["commit", "-m", "init"], cwd=r)
    (r / ".claude").mkdir()
    return r


def _seed_ref(repo: Path, uuid: str) -> tuple[Path, str]:
    """Write a live (marker-present) finalize-stash ref + a real stash for `uuid`."""
    name = f"execute-{uuid}-20260101T0000Z"
    marker = repo.resolve() / ".claude" / f".hm-loop-{name}"
    marker.write_text(f"{repo.resolve()}\n", encoding="utf-8")
    ref = repo / ".claude" / f".hm-finalize-stash-{name}"
    ref.write_text(
        "ref_sha: " + ("a" * 40) + "\n"
        f"base: {repo.resolve()}\n"
        f"session_marker: {marker}\n"
        f"session_uuid: {uuid}\n"
        "created_at: 2026-01-01T00:00:00+00:00\n",
        encoding="utf-8",
    )
    (repo / f"wip-{uuid}.txt").write_text(f"wip {uuid}\n")
    _git(["add", f"wip-{uuid}.txt"], cwd=repo)
    _git(["stash", "push", "-u", "-m", f"hm-finalize-{name}"], cwd=repo)
    return ref, name


def test_foreign_uuid_ref_preserved(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A live foreign-uuid ref + stash are PRESERVED when the owned-set is a
    DIFFERENT session's uuid — the cross-session contamination guard."""
    ref_b, name_b = _seed_ref(repo, "bbbbbbbbbbbb")
    monkeypatch.setenv("HM_OWNED_SESSION_UUIDS", "aaaaaaaaaaaa")  # a peer's uuid

    rc = worktree._cli_post_commit_pop([str(repo)])
    assert rc == 0
    # B (foreign) MUST be untouched — ref + stash both preserved.
    assert ref_b.exists(), "peer (foreign-uuid) ref must NOT be deleted"
    assert f"hm-finalize-{name_b}" in _git(["stash", "list"], cwd=repo).stdout, (
        "peer (foreign-uuid) stash must NOT be popped — contamination guard"
    )


def test_empty_owned_set_preserves_uuid_ref(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-003: an EMPTY owned-set fail-safe-SKIPs a uuid'd ref (does NOT fall back
    to the old marker-present pop)."""
    ref_a, name_a = _seed_ref(repo, "aaaaaaaaaaaa")
    monkeypatch.setenv("HM_OWNED_SESSION_UUIDS", "")

    rc = worktree._cli_post_commit_pop([str(repo)])
    assert rc == 0
    assert ref_a.exists(), "uuid'd ref must be PRESERVED on empty owned-set (fail-safe)"
    assert f"hm-finalize-{name_a}" in _git(["stash", "list"], cwd=repo).stdout, (
        "uuid'd stash must NOT pop on empty owned-set (the guard-drop fail-safe)"
    )


def test_crumb_feeds_owned_set(repo: Path) -> None:
    """The wrapup flow source: owned-crumb-read returns the slug's recorded uuids,
    which become HM_OWNED_SESSION_UUIDS."""
    worktree._owned_crumb_add(repo, "myslug", "aaaaaaaaaaaa")
    worktree._owned_crumb_add(repo, "myslug", "cccccccccccc")
    assert worktree._owned_crumb_read(repo, "myslug") == [
        "aaaaaaaaaaaa",
        "cccccccccccc",
    ]
    # A peer slug's crumb is independent (per-task isolation).
    assert worktree._owned_crumb_read(repo, "peerslug") == []
