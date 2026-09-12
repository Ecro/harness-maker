"""Observability writers file at the BASE repo root, never the worktree (2026-09-12).

A task worktree's `.claude/observability/` is gitignored and deleted at `task-land`, so a
row written there is a row lost. `stage_agent_ledger` and `second_opinion_invoke` already
resolved base; `review_telemetry emit` (cwd-rooted) and `spec_need record` (`--root <WT>`)
did not, and both losses were measured in consuming projects before this test existed.
The third gate covers the opposite drift: files git still TRACKS under the ignored dir.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness_maker import readiness, review_telemetry, spec_need


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=30, check=True
    )
    return proc.stdout


def _repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    base = tmp_path / "base"
    base.mkdir()
    _git(base, "init", "-q", "-b", "main")
    _git(base, "config", "user.email", "t@t")
    _git(base, "config", "user.name", "t")
    (base / "README.md").write_text("x\n", encoding="utf-8")
    _git(base, "add", "README.md")
    _git(base, "commit", "-q", "-m", "init")
    wt = base / ".worktrees" / "slug"
    wt.parent.mkdir()
    _git(base, "worktree", "add", "-q", "-b", "hm/slug", str(wt))
    return base, wt


_ROW = {
    "ts": "2026-09-12T00:00:00Z",
    "slug": "s",
    "round": 1,
    "pass1_n": 0,
    "pass2_kept_n": 0,
    "consensus_passed_n": 0,
    "wall_time_ms": 1,
    "build_break_count": 0,
    "auto_fix_reverted_n": 0,
}


def test_review_emit_from_a_worktree_files_at_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base, wt = _repo_with_worktree(tmp_path)
    src = tmp_path / "row.json"
    src.write_text(json.dumps(_ROW), encoding="utf-8")
    monkeypatch.chdir(wt)

    assert review_telemetry.main(["emit", "--file", str(src)]) == 0

    written = Path(capsys.readouterr().out.strip()).resolve()
    assert written.is_relative_to(base.resolve() / ".claude" / "observability")
    assert not written.is_relative_to(wt.resolve())
    assert not (wt / ".claude" / "observability").exists()


def test_review_emit_outside_git_keeps_the_cwd_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Git-less = cwd, unchanged: every existing cwd-based test of `emit` still holds."""
    src = tmp_path / "row.json"
    src.write_text(json.dumps(_ROW), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert review_telemetry.main(["emit", "--file", str(src)]) == 0
    written = Path(capsys.readouterr().out.strip()).resolve()
    assert written.is_relative_to(tmp_path.resolve() / ".claude" / "observability")


def test_spec_need_record_from_a_worktree_root_files_at_base(tmp_path: Path) -> None:
    base, wt = _repo_with_worktree(tmp_path)

    spec_need.record_spec_need("add", "feat", "why", wt)

    assert (base / ".claude" / "observability" / "spec-need-feat.jsonl").is_file()
    assert not (wt / ".claude" / "observability").exists()


def test_spec_need_marker_stays_in_the_worktree(tmp_path: Path) -> None:
    """Gate state is read back where it is written — it must NOT follow the ledger to base."""
    base, wt = _repo_with_worktree(tmp_path)
    spec_need.write_marker(wt, "slug", "add", "feat", "abc", "h")
    assert spec_need.marker_path(wt, "slug").is_file()
    assert not spec_need.marker_path(base, "slug").exists()


def _repo_with_tracked_snapshot(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    obs = repo / ".claude" / "observability"
    obs.mkdir(parents=True)
    (obs / "dashboard.md").write_text("old\n", encoding="utf-8")
    (obs / "review-2026-05-26.jsonl").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "snapshot")
    # The rule arrives AFTER the commit — exactly how the consuming projects got here.
    (repo / ".gitignore").write_text(".claude/observability/\n", encoding="utf-8")
    return repo


def test_tracked_but_ignored_lists_the_snapshot_and_clears_after_untrack(tmp_path: Path) -> None:
    repo = _repo_with_tracked_snapshot(tmp_path)
    assert readiness.tracked_but_ignored_observability(repo) == [
        ".claude/observability/dashboard.md",
        ".claude/observability/review-2026-05-26.jsonl",
    ]
    _git(repo, "rm", "-r", "-q", "--cached", ".claude/observability")
    assert readiness.tracked_but_ignored_observability(repo) == []


def test_tracked_but_ignored_is_none_outside_git(tmp_path: Path) -> None:
    assert readiness.tracked_but_ignored_observability(tmp_path) is None


def test_health_signal_names_paths_and_remediation(tmp_path: Path) -> None:
    repo = _repo_with_tracked_snapshot(tmp_path)
    sig = {s.id: s for s in readiness._dim_guardrails(repo).signals}[
        "observability_tracked_but_ignored"
    ]
    assert sig.passed is False
    assert ".claude/observability/dashboard.md" in sig.evidence
    assert sig.action is not None
    assert "git rm -r --cached .claude/observability/dashboard.md" in sig.action


def test_health_signal_is_not_applicable_outside_git(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    sig = {s.id: s for s in readiness._dim_guardrails(tmp_path).signals}[
        "observability_tracked_but_ignored"
    ]
    assert sig.passed is True
    assert sig.not_applicable is True
