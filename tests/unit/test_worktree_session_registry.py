"""Phase 1 (ADR-004, ADR-008): session registry + feature-branch-workflow flag.

session_uuid is the primary identity; pid is a liveness HINT only. The registry
read-modify-write is lock-serialized + atomic. A live mismatched-UUID row is never
deleted. The flag defaults to False on an absent key (conservative — old model + warn).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from harness_maker import worktree


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(".claude/\n.worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    (repo / ".claude").mkdir()
    return repo


def _reg(repo: Path, task: str, branch: str, wt: str, uuid: str) -> None:
    worktree.register_session(
        repo, task=task, branch=branch, wt=wt, session_uuid=uuid, pid=os.getpid()
    )


# ── flag helper ──────────────────────────────────────────────────────────────


def test_flag_absent_returns_false_and_warns_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    # No key of ANY generation — the only shape that reaches the absent-case warning.
    # (`scope: [execute]` is no longer "absent": it is a legacy rung the reader honors,
    # which is what keeps an un-re-rendered harness working.)
    (repo / ".claude" / "harness.yaml").write_text("preset: Production\n")
    worktree._reset_flag_warning_state()  # test hook: clear the once-per-process guard

    assert worktree.worktree_enabled(repo) is False
    assert worktree.worktree_enabled(repo) is False  # second call

    warnings = capsys.readouterr().err
    assert warnings.count("no worktree.enabled key") == 1  # warned exactly once


def test_legacy_scope_is_honoured_not_treated_as_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An un-re-rendered harness keeps working: `scope: [execute]` meant isolation was
    on for execute, so the reader resolves True rather than warning about an absent key."""
    repo = _repo(tmp_path)
    (repo / ".claude" / "harness.yaml").write_text("worktree:\n  scope: [execute]\n")
    worktree._reset_flag_warning_state()
    assert worktree.worktree_enabled(repo) is True
    assert capsys.readouterr().err == ""


def test_flag_true_round_trips(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".claude" / "harness.yaml").write_text(
        "worktree:\n  scope: [execute]\n  feature_branch_workflow: true\n"
    )
    assert worktree._feature_branch_workflow_enabled(repo) is True


def test_flag_false_explicit(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".claude" / "harness.yaml").write_text("worktree:\n  feature_branch_workflow: false\n")
    assert worktree._feature_branch_workflow_enabled(repo) is False


# ── registry: register / read / release ──────────────────────────────────────


def test_register_then_read_round_trips(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    worktree.register_session(
        repo,
        task="foo",
        branch="hm/foo",
        wt=str(repo / ".worktrees" / "foo"),
        session_uuid="uuid-foo-0001",
        pid=os.getpid(),
    )
    rows = worktree._read_sessions(repo)
    assert len(rows) == 1
    assert rows[0].task == "foo"
    assert rows[0].session_uuid == "uuid-foo-0001"
    # atomic write produced valid JSON
    data = json.loads((repo / ".claude" / ".hm-sessions.json").read_text())
    assert isinstance(data, list)


def test_release_removes_only_matching_uuid(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _reg(repo, "a", "hm/a", "wta", "u-a")
    _reg(repo, "b", "hm/b", "wtb", "u-b")
    worktree.release_session(repo, session_uuid="u-a")
    rows = worktree._read_sessions(repo)
    assert [r.session_uuid for r in rows] == ["u-b"]


def test_register_idempotent_by_uuid_replaces_in_place(tmp_path: Path) -> None:
    """Re-registering the same session_uuid replaces the row (no duplicate)."""
    repo = _repo(tmp_path)
    _reg(repo, "old", "hm/old", "wt-old", "u-same")
    _reg(repo, "new", "hm/new", "wt-new", "u-same")
    rows = worktree._read_sessions(repo)
    assert len(rows) == 1
    assert rows[0].task == "new"
    assert rows[0].branch == "hm/new"


def test_reclaim_preserves_row_under_pid_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pid reuse (a recorded pid now owned by an unrelated process) must NOT drop a
    row whose worktree is still present — preserve-biased, never a false drop."""
    repo = _repo(tmp_path)
    wt = repo / ".worktrees" / "reused"
    wt.mkdir(parents=True)
    worktree.register_session(
        repo, task="reused", branch="hm/reused", wt=str(wt), session_uuid="u-reused", pid=4242
    )
    monkeypatch.setattr(worktree, "_pid_alive", lambda _pid: True)  # simulate pid-reuse
    worktree.reclaim_stale(repo)
    assert [r.session_uuid for r in worktree._read_sessions(repo)] == ["u-reused"]


def test_read_missing_file_is_empty(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert worktree._read_sessions(repo) == []


def test_read_corrupt_file_tolerated(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".claude" / ".hm-sessions.json").write_text("{ this is not json")
    assert worktree._read_sessions(repo) == []  # tolerant, no raise


# ── stale-reclaim: session_uuid primary, pid liveness-hint only ───────────────


def test_reclaim_drops_row_with_missing_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    worktree.register_session(
        repo,
        task="gone",
        branch="hm/gone",
        wt=str(repo / ".worktrees" / "missing"),
        session_uuid="u-gone",
        pid=os.getpid(),
    )
    worktree.reclaim_stale(repo)
    assert worktree._read_sessions(repo) == []  # worktree dir missing → reclaimed


def test_reclaim_keeps_row_with_live_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = repo / ".worktrees" / "live"
    wt.mkdir(parents=True)
    worktree.register_session(
        repo,
        task="live",
        branch="hm/live",
        wt=str(wt),
        session_uuid="u-live",
        pid=os.getpid(),
    )
    worktree.reclaim_stale(repo)
    assert [r.session_uuid for r in worktree._read_sessions(repo)] == ["u-live"]


def test_reclaim_never_drops_live_pid_even_if_worktree_present(tmp_path: Path) -> None:
    """A live pid + present worktree row must survive reclaim (no false drop)."""
    repo = _repo(tmp_path)
    wt = repo / ".worktrees" / "alive"
    wt.mkdir(parents=True)
    worktree.register_session(
        repo,
        task="alive",
        branch="hm/alive",
        wt=str(wt),
        session_uuid="u-alive",
        pid=os.getpid(),
    )
    worktree.reclaim_stale(repo)
    assert any(r.session_uuid == "u-alive" for r in worktree._read_sessions(repo))


# ── field validation (adversarial) ───────────────────────────────────────────


def test_register_rejects_traversal_and_nul(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    worktree.register_session(
        repo,
        task="../../etc/passwd",
        branch="hm/x\ninjected",
        wt="w\x00t",
        session_uuid="u-bad",
        pid=os.getpid(),
    )
    # adversarial row dropped (never raises); registry stays clean
    rows = worktree._read_sessions(repo)
    assert all(
        "../" not in r.task and "\n" not in r.branch and "\x00" not in r.worktree for r in rows
    )


# ── churn / dirty-base exclusion ──────────────────────────────────────────────


def test_registry_file_does_not_trip_dirty_base_guard(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _reg(repo, "c", "hm/c", "wtc", "u-c")
    # the registry is operational churn → must NOT count as user dirt
    assert worktree._has_user_dirty_state(repo) is False


# ── concurrency: lock-serialized read-modify-write ────────────────────────────


def test_concurrent_mutate_does_not_clobber_live_claim(tmp_path: Path) -> None:
    """Two sequential registers via the locked mutate path both survive (no lost update)."""
    repo = _repo(tmp_path)
    _reg(repo, "p", "hm/p", "wtp", "u-p")
    _reg(repo, "q", "hm/q", "wtq", "u-q")
    uuids = {r.session_uuid for r in worktree._read_sessions(repo)}
    assert uuids == {"u-p", "u-q"}  # neither register clobbered the other
