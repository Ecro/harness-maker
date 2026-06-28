"""Unit tests for git_disposition: post-render commit/ignore detection + idempotent gitignore."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness_maker import git_disposition as gd


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")


def _write(p: Path, content: str = "x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _make_harness(
    repo: Path,
    *,
    targets: tuple[str, ...] = ("claude-code",),
    files: tuple[str, ...] = (".claude/harness.yaml", ".claude/agents/a.md"),
    manifest: bool = True,
) -> None:
    for f in files:
        _write(repo / f)
    # Written LAST so a ".claude/harness.yaml" entry in `files` (content "x")
    # does not clobber the real targets body.
    tlist = "[" + ", ".join(targets) + "]"
    _write(repo / ".claude/harness.yaml", f"targets: {tlist}\npreset: Side\n")
    if manifest:
        data = {"generated_by": "harness-maker", "version": "0.0.0", "files": sorted(set(files))}
        _write(repo / ".claude/.harness-manifest.json", json.dumps(data))


# ── resolve_target_roots ──────────────────────────────────────────────────


def test_resolve_target_roots_claude_only() -> None:
    assert gd.resolve_target_roots(["claude-code"]) == [".claude/"]


def test_resolve_target_roots_multi() -> None:
    roots = gd.resolve_target_roots(["claude-code", "cursor", "codex"])
    assert roots == [".claude/", ".cursor/", ".codex/", ".agents/", "AGENTS.md"]


# ── compute_git_status ────────────────────────────────────────────────────


def test_non_git_dir(tmp_path: Path) -> None:
    _make_harness(tmp_path)
    s = gd.compute_git_status(tmp_path)
    assert s.is_git is False
    assert s.decision_needed is False
    assert s.offer_stage is False


def test_unborn_repo_undecided_no_crash(tmp_path: Path) -> None:
    # check-ignore returns rc=1 (not ignored) on every file — must NOT crash.
    _init_repo(tmp_path)
    _make_harness(tmp_path)
    s = gd.compute_git_status(tmp_path)
    assert s.is_git is True
    assert s.prior_decision == "undecided"
    assert s.decision_needed is True
    assert ".claude/harness.yaml" in s.untracked_files


def test_tracked_is_commit(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _make_harness(tmp_path)
    _git(tmp_path, "add", ".claude")
    _git(tmp_path, "commit", "-qm", "add harness")
    s = gd.compute_git_status(tmp_path)
    assert s.prior_decision == "commit"
    assert s.decision_needed is False
    assert s.offer_stage is False


def test_commit_mode_new_file_offers_stage(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _make_harness(tmp_path)
    _git(tmp_path, "add", ".claude")
    _git(tmp_path, "commit", "-qm", "add harness")
    # a re-render adds a new agent file (manifest + disk), untracked.
    _make_harness(
        tmp_path,
        files=(".claude/harness.yaml", ".claude/agents/a.md", ".claude/agents/new.md"),
    )
    s = gd.compute_git_status(tmp_path)
    assert s.prior_decision == "commit"
    assert s.decision_needed is False  # no full re-nag
    assert s.offer_stage is True
    assert ".claude/agents/new.md" in s.untracked_files
    assert ".claude/agents/a.md" not in s.untracked_files  # tracked file not re-listed


def test_exact_file_ignore_still_undecided(tmp_path: Path) -> None:
    # .gitignore ignores ONLY harness.yaml — agents/a.md remains undecided.
    _init_repo(tmp_path)
    _make_harness(tmp_path)
    _write(tmp_path / ".gitignore", ".claude/harness.yaml\n")
    s = gd.compute_git_status(tmp_path)
    assert s.prior_decision == "undecided"
    assert s.decision_needed is True
    assert ".claude/agents/a.md" in s.untracked_files


def test_parent_dir_ignore_is_ignore(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _make_harness(tmp_path)
    _write(tmp_path / ".gitignore", ".claude/\n")
    s = gd.compute_git_status(tmp_path)
    assert s.prior_decision == "ignore"
    assert s.decision_needed is False


def test_parent_ignore_with_negation_is_undecided(tmp_path: Path) -> None:
    # .claude/ ignored but harness.yaml un-ignored via negation → not all ignored.
    _init_repo(tmp_path)
    _make_harness(tmp_path)
    # NOTE: `.claude/*` (glob), NOT `.claude/` — git cannot re-include a file whose
    # parent *directory* is excluded, so a `.claude/` dir-exclude would keep harness.yaml
    # ignored despite the negation. `.claude/*` excludes children individually.
    _write(tmp_path / ".gitignore", ".claude/*\n!.claude/harness.yaml\n")
    s = gd.compute_git_status(tmp_path)
    assert s.prior_decision == "undecided"
    assert ".claude/harness.yaml" in s.untracked_files


def test_multi_target_roots_undecided(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _make_harness(
        tmp_path,
        targets=("claude-code", "cursor", "codex"),
        files=(".claude/harness.yaml", ".cursor/rules/r.mdc", ".codex/config.toml", "AGENTS.md"),
    )
    s = gd.compute_git_status(tmp_path)
    assert s.prior_decision == "undecided"
    assert "AGENTS.md" in s.untracked_files
    assert ".cursor/rules/r.mdc" in s.untracked_files


def test_manifest_absent_fallback(tmp_path: Path) -> None:
    # No manifest → fall back to the existing root dirs.
    _init_repo(tmp_path)
    _make_harness(tmp_path, manifest=False)
    s = gd.compute_git_status(tmp_path)
    assert s.is_git is True
    assert s.prior_decision == "undecided"


def test_churn_files_excluded_from_undecided(tmp_path: Path) -> None:
    # observability churn must not count as an undecided unit nor trigger offer_stage.
    _init_repo(tmp_path)
    _make_harness(
        tmp_path,
        files=(".claude/harness.yaml", ".claude/observability/log.md"),
    )
    _git(tmp_path, "add", ".claude/harness.yaml")
    _git(tmp_path, "commit", "-qm", "harness")
    s = gd.compute_git_status(tmp_path)
    assert s.prior_decision == "commit"
    assert s.offer_stage is False  # churn is not an undecided unit
    assert ".claude/observability/log.md" not in s.untracked_files


def test_traversal_path_excluded_from_units(tmp_path: Path) -> None:
    # A `..`-bearing manifest path must never reach a git probe (defense-in-depth).
    _init_repo(tmp_path)
    _make_harness(tmp_path, files=(".claude/harness.yaml", ".claude/../../etc/passwd"))
    s = gd.compute_git_status(tmp_path)
    assert ".claude/../../etc/passwd" not in s.untracked_files


# ── ignore_roots ──────────────────────────────────────────────────────────


def test_ignore_roots_idempotent_and_ignores(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _make_harness(tmp_path)
    first = gd.ignore_roots(tmp_path)
    assert ".claude/" in first
    gd.ignore_roots(tmp_path)  # second run — no duplicate line
    lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert lines.count(".claude/") == 1
    # state is now "ignore"
    assert gd.compute_git_status(tmp_path).prior_decision == "ignore"


def test_ignore_roots_multi_target(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _make_harness(
        tmp_path,
        targets=("claude-code", "cursor", "codex"),
        files=(".claude/harness.yaml", ".cursor/rules/r.mdc", ".codex/config.toml", "AGENTS.md"),
    )
    ignored = gd.ignore_roots(tmp_path)
    assert ".cursor/" in ignored
    assert "AGENTS.md" in ignored
    assert gd.compute_git_status(tmp_path).prior_decision == "ignore"


def test_ignore_roots_loud_fail_non_git(tmp_path: Path) -> None:
    _make_harness(tmp_path)  # no git init
    with pytest.raises(gd.GitDispositionError):
        gd.ignore_roots(tmp_path)
