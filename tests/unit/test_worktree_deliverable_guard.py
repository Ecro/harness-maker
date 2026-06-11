"""PLAN-worktree-deliverable-blocks-create ADR-001 — create-guard deliverable exemption.

`/hm:plan` writes deliverables (PLAN/RESEARCH/SPEC/REVIEW docs) to `work-docs/`
that `/hm:execute` depends on; they are excluded from the churn set so
`/hm:wrapup` can commit them, so they are ALWAYS uncommitted at `worktree
create` time. The create-guard forgives them PER-LINE (anchored full-match);
the finalize filter does NOT (they stay stash-preserved).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from harness_maker.worktree import (
    _has_user_dirty_state,
    _is_deliverable_path,
    _is_harness_artifact,
    _list_user_dirty_files,
)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    # .claude/ gitignored (mirrors real-world) but work-docs/ deliberately NOT —
    # deliverables are tracked so wrapup commits them. This is the bug surface.
    (repo / ".gitignore").write_text(".claude/\n.worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    cd = repo / ".claude"
    cd.mkdir()
    (cd / "harness.yaml").write_text("worktree:\n  scope: [execute]\n", encoding="utf-8")
    return repo


# ── _is_deliverable_path: anchored full-match ───────────────────────────────


def test_is_deliverable_path_matches_all_four_doc_types() -> None:
    assert _is_deliverable_path("work-docs/PLAN-foo.md")
    assert _is_deliverable_path("work-docs/RESEARCH-foo.md")
    assert _is_deliverable_path("work-docs/SPEC-foo.md")
    assert _is_deliverable_path("work-docs/REVIEW-foo-2026-06-12.md")
    assert _is_deliverable_path("specs/SPEC-foo.md")


def test_is_deliverable_path_anti_over_match_bak_sibling() -> None:
    """`.bak` sibling NOT forgiven — mirrors the EXACT-match churn discipline."""
    assert not _is_deliverable_path("work-docs/PLAN-foo.md.bak")


def test_is_deliverable_path_anti_over_match_non_deliverable() -> None:
    assert not _is_deliverable_path("work-docs/random.md")
    assert not _is_deliverable_path("work-docs/notes.txt")
    assert not _is_deliverable_path("src/harness_maker/PLAN-foo.md")
    assert not _is_deliverable_path("specs/SPEC-foo.machine.yaml")


def test_is_deliverable_path_anti_over_match_nested_dir() -> None:
    """`[^/]+` anchoring: a nested user dir whose name starts with a deliverable
    prefix must NOT be forgiven (only FLAT deliverables are /hm:plan output)."""
    assert not _is_deliverable_path("work-docs/PLAN-experiments/notes.md")
    assert not _is_deliverable_path("specs/SPEC-archive/old.md")


def test_is_deliverable_path_non_default_work_docs_dir_not_covered() -> None:
    """NON-GOAL (ADR-001): a non-default work_docs.dir is NOT covered — same
    accepted limitation as the churn-filter (pure porcelain predicate, no
    harness.yaml access). Documented behavior asserted, not aspirational."""
    assert not _is_deliverable_path("docs/plans/PLAN-foo.md")


# ── create-guard: per-line forgiveness ──────────────────────────────────────


def test_lone_deliverable_does_not_trip_create_guard(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "work-docs").mkdir()
    (repo / "work-docs" / "PLAN-feature.md").write_text("plan body")
    assert _has_user_dirty_state(repo) is False


def test_code_wip_still_blocks(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "src.py").write_text("code wip")
    assert _has_user_dirty_state(repo) is True


def test_mixed_deliverable_plus_code_blocks_and_lists_only_code(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "work-docs").mkdir()
    (repo / "work-docs" / "PLAN-feature.md").write_text("plan")
    (repo / "src.py").write_text("code wip")
    assert _has_user_dirty_state(repo) is True
    dirty = _list_user_dirty_files(repo)
    assert "src.py" in dirty
    assert "work-docs/PLAN-feature.md" not in dirty


# ── finalize filter invariant: deliverables stay user-dirt (preserved) ──────


def test_finalize_filter_still_treats_deliverable_as_user_dirt() -> None:
    """ADR-001 invariant — `_is_harness_artifact` (finalize) must NOT forgive
    deliverables, so the finalize stash still PRESERVES them. Only the
    create-guard forgives."""
    assert _is_harness_artifact("?? work-docs/PLAN-foo.md") is False


# ── CLI integration: create proceeds with a lone deliverable dirty ──────────


def _run_create(repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "create", "execute", str(repo), *extra],
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_cli_create_proceeds_with_uncommitted_deliverable(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "work-docs").mkdir()
    (repo / "work-docs" / "PLAN-feature.md").write_text("plan body")
    proc = _run_create(repo)
    assert proc.returncode == 0, f"deliverable wrongly blocked create: {proc.stderr}"
    assert ".worktrees/execute-" in proc.stdout
