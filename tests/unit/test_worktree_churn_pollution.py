"""PLAN-worktree-base-artifact-pollution — keep-base-clean.

Churn paths (observability, iter-receipts, loop-context, render-manifest,
machine memory tiers) must be (a) recognized by both dirt-filters so they
neither block `create` nor trigger a finalize stash, and (b) appended to the
user's .gitignore. Genuine user `.claude/` edits and deliverables
(PLAN/REVIEW/RESEARCH/SPEC) must stay "dirt" so they are preserved/committed.
Orphan finalize-stash refs whose stash object is gone must be drained.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker import worktree
from harness_maker.worktree import (
    _HARNESS_CHURN_DIRS,
    _HARNESS_CHURN_FILES,
    _HARNESS_GITIGNORE_PATTERNS,
    _ensure_harness_gitignore,
    _is_create_guard_harness_artifact,
    _is_harness_artifact,
    _stash_object_exists,
)


def _git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )
    return cp.stdout.strip()


def _repo(tmp_path: Path, gitignore: str = ".worktrees/\n") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(gitignore, encoding="utf-8")
    (repo / "README.md").write_text("x\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _porcelain(path: str, code: str = "?? ") -> str:
    """Build a `git status --porcelain` v1 line (XY + space + path)."""
    return f"{code}{path}"


# ── Phase 2: finalize filter recognizes churn ───────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        ".claude/observability/metrics-2026-05-28.jsonl",
        ".claude/observability/security/findings-2026-05-28.jsonl",
        ".claude/.hm-iter-receipts/iter-1/execute.json",
        ".claude/loop-specs/foo.yaml",
        ".claude/.hm-session-uuid",
        ".claude/.hm-render-manifest.jsonl",
        ".claude/memory/semantic/index.jsonl",
        ".claude/memory/episodic/2026-05-28.jsonl",
        ".claude/memory/profile/profile.json",
        "work-docs/loop-context/some-slug.yaml",
        "work-docs/p5-batch-state.yaml",
    ],
)
def test_is_harness_artifact_recognizes_churn(path: str) -> None:
    assert _is_harness_artifact(_porcelain(path)) is True


@pytest.mark.parametrize(
    "path",
    [
        ".claude/agents/custom-reviewer.md",
        ".claude/skills/my-skill/SKILL.md",
        ".claude/commands/hm/custom.md",
        ".claude/harness.yaml",
        ".claude/memory/wiki.md",
        ".claude/memory/failures.md",
    ],
)
def test_is_harness_artifact_preserves_user_claude_edits(path: str) -> None:
    # Narrow-filter invariant: genuine user .claude/ edits stay "dirt" so the
    # finalize stash preserves them (worktree.py:609-617 design constraint).
    assert _is_harness_artifact(_porcelain(path)) is False


@pytest.mark.parametrize(
    "path",
    [
        "work-docs/PLAN-foo.md",
        "work-docs/REVIEW-foo-2026-05-28.md",
        "work-docs/RESEARCH-foo.md",
        "specs/SPEC-foo.md",
        "specs/SPEC-foo.machine.yaml",
    ],
)
def test_is_harness_artifact_preserves_deliverables(path: str) -> None:
    assert _is_harness_artifact(_porcelain(path)) is False


def test_is_harness_artifact_forgives_gitignore() -> None:
    # ADR-002: `.gitignore` is co-managed (the migration appends churn patterns
    # to it). Its `M` must not trip the dirty-base guard nor get stashed —
    # otherwise the migration itself recreates the churn it removes.
    assert _is_harness_artifact(_porcelain(".gitignore", " M ")) is True


# ── Phase 2: create-guard inherits churn via delegation ─────────────────────


@pytest.mark.parametrize(
    "path",
    ["work-docs/loop-context/some-slug.yaml", "work-docs/p5-batch-state.yaml"],
)
def test_create_guard_forgives_workdocs_churn(path: str) -> None:
    # ADR-003: committed-then-modified work-docs/ churn must NOT block create.
    assert _is_create_guard_harness_artifact(_porcelain(path, " M ")) is True


def test_create_guard_still_blocks_user_workdocs_deliverable() -> None:
    # A real deliverable / user file under work-docs/ still counts as dirt.
    assert _is_create_guard_harness_artifact(_porcelain("work-docs/PLAN-foo.md")) is False


# ── Phase 2: file churn is matched EXACTLY, not by prefix (REVIEW consensus) ──


@pytest.mark.parametrize(
    "path",
    [
        "work-docs/p5-batch-state.yaml.bak",
        ".claude/.hm-session-uuid-notes",
        ".claude/.hm-render-manifest.jsonl.old",
    ],
)
def test_is_harness_artifact_file_churn_no_prefix_collision(path: str) -> None:
    # A sibling that merely starts with a file-churn name must NOT be forgiven.
    assert _is_harness_artifact(_porcelain(path)) is False


# ── Phase 2: porcelain edge cases (rename / quoted / empty) ──────────────────


def test_is_harness_artifact_rename_uses_destination() -> None:
    # Porcelain rename `R  old -> new` — classification follows the destination.
    line = "R  work-docs/old.yaml -> work-docs/loop-context/x.yaml"
    assert _is_harness_artifact(line) is True
    line2 = "R  work-docs/loop-context/x.yaml -> work-docs/PLAN-foo.md"
    assert _is_harness_artifact(line2) is False


def test_is_harness_artifact_quoted_path() -> None:
    # git quotes paths with special chars; the quotes must be stripped.
    assert _is_harness_artifact('?? "work-docs/loop-context/sp ace.yaml"') is True


def test_is_harness_artifact_empty_or_short_line() -> None:
    assert _is_harness_artifact("") is False
    assert _is_harness_artifact("?? ") is False


# ── Phase 2: sync guard (single source of truth) ────────────────────────────


def test_churn_gitignore_and_filter_sets_in_sync() -> None:
    assert _HARNESS_GITIGNORE_PATTERNS == _HARNESS_CHURN_DIRS + _HARNESS_CHURN_FILES
    assert all(p.endswith("/") for p in _HARNESS_CHURN_DIRS)  # dirs = prefix match
    assert all(not p.endswith("/") for p in _HARNESS_CHURN_FILES)  # files = exact
    # disjoint — no path is both a dir-prefix and an exact-file entry
    assert not (set(_HARNESS_CHURN_DIRS) & set(_HARNESS_CHURN_FILES))


# ── Phase 1: gitignore consolidation ────────────────────────────────────────


def test_ensure_harness_gitignore_appends_all_and_is_idempotent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _ensure_harness_gitignore(repo)
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    for pattern in _HARNESS_GITIGNORE_PATTERNS:
        assert pattern in text.splitlines(), f"{pattern} not appended"

    _ensure_harness_gitignore(repo)  # second call must not duplicate
    text2 = (repo / ".gitignore").read_text(encoding="utf-8")
    for pattern in _HARNESS_GITIGNORE_PATTERNS:
        assert text2.splitlines().count(pattern) == 1, f"{pattern} duplicated"


def test_ensure_harness_gitignore_subsumption_when_claude_dir_ignored(tmp_path: Path) -> None:
    # When `.claude/` is already dir-ignored, the `.claude/...` churn patterns
    # are subsumed (skipped); the work-docs/ patterns are still appended.
    repo = _repo(tmp_path, gitignore=".worktrees/\n.claude/\n")
    _ensure_harness_gitignore(repo)
    lines = (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".claude/.hm-session-uuid" not in lines  # subsumed by `.claude/`
    assert ".claude/observability/" not in lines  # subsumed
    assert "work-docs/loop-context/" in lines  # not subsumed → appended


# ── Phase 4: orphan stash-ref drain ─────────────────────────────────────────


def test_stash_object_exists(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    head = _git(["rev-parse", "HEAD"], repo)
    assert _stash_object_exists(repo, head) is True
    assert _stash_object_exists(repo, "a" * 40) is False


def test_prune_drains_ref_whose_stash_object_is_gone(tmp_path: Path) -> None:
    # ADR-005: a finalize-stash ref pointing at a vanished stash object is pure
    # cruft (nothing to restore) → drained, even though content is not in HEAD.
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir()
    wt_name = "execute-deadbeef1234-20260525T0000Z"
    marker = claude / f".hm-loop-{wt_name}"  # intentionally NOT created (absent)
    ref_file = worktree._write_stash_ref_file(repo, wt_name, "a" * 40, marker)
    assert ref_file.exists()

    report = worktree.prune_stale(repo)

    assert ref_file in report.removed_stash_refs
    assert not ref_file.exists()


def test_prune_drains_ref_whose_base_dir_is_gone_without_crashing(tmp_path: Path) -> None:
    # REVIEW: a ref recording a base dir that no longer exists (e.g. a removed
    # sibling repo) must NOT crash prune_stale with an uncaught FileNotFoundError
    # (git cwd missing). The gone base = unreachable stash = drainable cruft.
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    claude.mkdir()
    gone_base = tmp_path / "removed-sibling"  # never created
    wt_name = "execute-cafebabe5678-20260525T0000Z"
    marker = claude / f".hm-loop-{wt_name}"  # absent
    ref_file = worktree._write_stash_ref_file(repo, wt_name, "b" * 40, marker)
    # Redirect the ref's recorded base at the non-existent dir (line-based, so
    # it reliably exercises the `not ref_base.is_dir()` guard).
    lines = ref_file.read_text(encoding="utf-8").splitlines()
    ref_file.write_text(
        "\n".join(f"base: {gone_base}" if ln.startswith("base:") else ln for ln in lines) + "\n",
        encoding="utf-8",
    )

    report = worktree.prune_stale(repo)  # must not raise

    assert ref_file in report.removed_stash_refs
    assert not ref_file.exists()
