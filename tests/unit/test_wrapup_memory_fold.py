"""commit_base_memory — fold base-written human memory tiers into the fresh squash.

Closes the per-task feature-branch seam where wrapup memory (written to BASE by
memory_md) is never committed. The helper is gated (ADR-004): it amends ONLY when
HEAD == the expected fresh squash AND nothing outside the tier pathspec is staged.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker.worktree import _HUMAN_MEMORY_TIER_PATHSPEC, commit_base_memory


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(repo), check=True, capture_output=True, text=True
    ).stdout


def _init_repo(tmp_path: Path, *, gitignore_claude: bool = False) -> tuple[Path, str, str]:
    """Build a repo simulating a post-task-land state.

    Returns (repo, pre_tip C0, squash_head C1). wiki.md + failures.md are tracked at
    C0 (force-added when `gitignore_claude` blankets `.claude/`); C1 is the fresh
    squash commit (HEAD).
    """
    repo = tmp_path / "base"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    mem = repo / ".claude" / "memory"
    (mem / "session").mkdir(parents=True)
    (mem / "wiki.md").write_text("# wiki\nentry-0\n")
    (mem / "failures.md").write_text("# failures\nfail-0\n")
    (repo / "code.py").write_text("x = 0\n")
    if gitignore_claude:
        (repo / ".gitignore").write_text(".claude/\n")
        _git(repo, "add", "-f", ".claude/memory/wiki.md", ".claude/memory/failures.md")
        _git(repo, "add", "code.py", ".gitignore")
    else:
        _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "C0 base tip")
    c0 = _git(repo, "rev-parse", "HEAD").strip()
    # C1 = the fresh squash commit (a code change), HEAD
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "code.py")
    _git(repo, "commit", "-q", "-m", "C1 squash")
    c1 = _git(repo, "rev-parse", "HEAD").strip()
    return repo, c0, c1


def _blob_at_head(repo: Path, path: str) -> str:
    return _git(repo, "show", f"HEAD:{path}")


def test_fold_memory_into_squash_commit(tmp_path: Path) -> None:
    """AC-001: dirty tracked tiers fold into the expect-head squash; one new commit."""
    repo, c0, c1 = _init_repo(tmp_path)
    (repo / ".claude" / "memory" / "wiki.md").write_text("# wiki\nentry-0\nentry-1\n")
    rc = commit_base_memory(repo, expect_head=c1)
    assert rc == 0
    # amend does not ADD a commit: still exactly one commit on top of the pre-tip C0
    assert _git(repo, "rev-list", "--count", f"{c0}..HEAD").strip() == "1"
    # the folded memory is in the (rewritten) squash commit
    assert "entry-1" in _blob_at_head(repo, ".claude/memory/wiki.md")
    # working tree no longer dirty for the tier
    assert ".claude/memory/wiki.md" not in _git(repo, "status", "--porcelain")


def test_fold_memory_idempotent_noop(tmp_path: Path) -> None:
    """AC-002: re-run with clean memory creates no commit and exits 0."""
    repo, _c0, c1 = _init_repo(tmp_path)
    (repo / ".claude" / "memory" / "failures.md").write_text("# failures\nfail-0\nfail-1\n")
    assert commit_base_memory(repo, expect_head=c1) == 0
    head_after_first = _git(repo, "rev-parse", "HEAD").strip()
    # second run: nothing modified → no-op, HEAD unchanged
    assert commit_base_memory(repo, expect_head=head_after_first) == 0
    assert _git(repo, "rev-parse", "HEAD").strip() == head_after_first


def test_fold_memory_force_adds_gitignored_tracked_tiers(tmp_path: Path) -> None:
    """AC-003: a force-tracked wiki.md under a blanket .claude/ ignore still commits."""
    repo, _c0, c1 = _init_repo(tmp_path, gitignore_claude=True)
    (repo / ".claude" / "memory" / "wiki.md").write_text("# wiki\nentry-0\nignored-but-tracked\n")
    rc = commit_base_memory(repo, expect_head=c1)
    assert rc == 0
    assert "ignored-but-tracked" in _blob_at_head(repo, ".claude/memory/wiki.md")


def test_fold_refuses_unexpected_head_or_foreign_staged(tmp_path: Path) -> None:
    """AC-005: refuse to amend when HEAD != expect_head OR foreign content is staged."""
    # (a) HEAD is not the expected fresh squash → refuse, HEAD unchanged
    repo, c0, c1 = _init_repo(tmp_path)
    (repo / ".claude" / "memory" / "wiki.md").write_text("# wiki\nentry-0\nx\n")
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    assert commit_base_memory(repo, expect_head=c0) != 0  # c0 is not HEAD
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before
    assert "x\n" not in _blob_at_head(repo, ".claude/memory/wiki.md")  # not folded

    # (b) a foreign (non-tier) path is already staged → refuse, foreign stays staged
    repo2, _c0b, c1b = _init_repo(tmp_path / "two")
    (repo2 / "code.py").write_text("x = 99\n")
    _git(repo2, "add", "code.py")  # foreign staged content
    (repo2 / ".claude" / "memory" / "wiki.md").write_text("# wiki\nentry-0\ny\n")
    head_before2 = _git(repo2, "rev-parse", "HEAD").strip()
    assert commit_base_memory(repo2, expect_head=c1b) != 0
    assert _git(repo2, "rev-parse", "HEAD").strip() == head_before2
    assert "code.py" in _git(repo2, "diff", "--cached", "--name-only")  # still staged


def test_fold_force_adds_untracked_session_tier(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-003 (revised): an untracked-and-ignored session/<today>.md IS folded (tier-bounded).

    This closes the seam for the richest per-task tier — memory_md creates today's session
    file fresh, so it is untracked-and-ignored on first write and `ls-files -m` misses it.
    """
    repo, _c0, c1 = _init_repo(tmp_path, gitignore_claude=True)
    (repo / ".claude" / "memory" / "wiki.md").write_text("# wiki\nentry-0\nz\n")
    # a brand-new session file, untracked + ignored (blanket .claude/)
    (repo / ".claude" / "memory" / "session" / "2026-06-30.md").write_text("## session\n")
    # an untracked file OUTSIDE the tier must NEVER be newly tracked (narrow-filter invariant)
    (repo / ".claude" / "memory" / "semantic.md").write_text("machine churn\n")
    rc = commit_base_memory(repo, expect_head=c1)
    assert rc == 0
    out = capsys.readouterr().out
    assert "session skipped" not in out  # no skip class anymore
    # the untracked session file is now tracked + committed at HEAD
    assert ".claude/memory/session/2026-06-30.md" in _git(repo, "ls-files")
    assert "## session" in _blob_at_head(repo, ".claude/memory/session/2026-06-30.md")
    # the out-of-tier untracked file was NOT swept in
    assert ".claude/memory/semantic.md" not in _git(repo, "ls-files")


def test_fold_amend_is_fenced_and_pathspec_scoped() -> None:
    """REVIEW P1: the amend critical section is merge-fenced and the amend is pathspec-scoped.

    These two properties are what make the fold airtight against a concurrent session's
    fenced squash (sweep-in / peer-HEAD-rewrite — the count:3 contamination class). They
    cannot be exercised deterministically without real cross-process timing, so this guards
    the source against regression (same pattern as the worktree render/source gates).
    """
    import inspect

    src = inspect.getsource(commit_base_memory)
    assert "_acquire_merge_fence(base" in src, "amend critical section must hold the merge fence"
    # the amend must be pathspec-scoped (`--only -- <paths>`), never a bare whole-index amend
    assert '"--only"' in src, "amend must be scoped to the memory pathspec via --only"
    bare_amend = '_git("commit", "--amend", "--no-edit")'
    assert bare_amend not in src, "a bare whole-index --amend re-opens the sweep-in race"


def test_fold_does_not_mislabel_tracked_unchanged_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REVIEW P3: a tracked-but-unchanged session file must NOT be reported as untracked."""
    repo, _c0, c1 = _init_repo(tmp_path, gitignore_claude=True)
    # a session file tracked at C0, on disk, unchanged this run
    sess = repo / ".claude" / "memory" / "session" / "2026-06-29.md"
    sess.write_text("## prior session\n")
    _git(repo, "add", "-f", ".claude/memory/session/2026-06-29.md")
    _git(repo, "commit", "-q", "-m", "track session")
    # advance HEAD again so the fresh-squash invariant holds for the fold target
    (repo / "code.py").write_text("x = 2\n")
    _git(repo, "add", "code.py")
    _git(repo, "commit", "-q", "-m", "C2")
    head = _git(repo, "rev-parse", "HEAD").strip()
    # now fold a wiki change; the tracked-unchanged session file is irrelevant
    (repo / ".claude" / "memory" / "wiki.md").write_text("# wiki\nentry-0\nfolded\n")
    assert commit_base_memory(repo, expect_head=head) == 0
    out = capsys.readouterr().out
    assert "2026-06-29.md" not in out, "tracked-unchanged session must not be flagged untracked"
    assert "session skipped" not in out


def test_tier_pathspec_corresponds_to_memory_md_writers() -> None:
    """The fold allowlist must cover exactly memory_md's human-tier writer targets."""
    from harness_maker import memory_md

    root = Path("/tmp/x")
    mem = memory_md._memory_dir(root)
    wiki_rel = str((mem / "wiki.md").relative_to(root))
    fail_rel = str((mem / "failures.md").relative_to(root))
    session_rel = str((mem / "session").relative_to(root))
    assert wiki_rel in _HUMAN_MEMORY_TIER_PATHSPEC
    assert fail_rel in _HUMAN_MEMORY_TIER_PATHSPEC
    assert session_rel in _HUMAN_MEMORY_TIER_PATHSPEC


def _render_wrapup(tmp_path: Path, *, flag_on: bool) -> str:
    from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    worktree = {"feature_branch_workflow": True} if flag_on else {}
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.SIDE, targets=[Target.CLAUDE_CODE], worktree=worktree),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return next(
        f.read_text(encoding="utf-8")
        for f in tmp_path.rglob("*.md")
        if str(f).endswith("stages/wrapup.md")
    )


def test_wrapup_memory_fold_gated_on_feature_branch_flag(tmp_path: Path) -> None:
    """AC-004: the fold step renders (exact launcher) only when the flag is on."""
    on = _render_wrapup(tmp_path / "on", flag_on=True)
    off = _render_wrapup(tmp_path / "off", flag_on=False)
    # flag-on: the exact full launcher + base arg + expect-head, inside the flag-on Step 7.7
    assert "uv run --with" in on
    assert (
        "python -m harness_maker.worktree commit-base-memory <BASE> --expect-head <SQUASH_SHA>"
        in on
    )
    assert "Fold base memory into the squash commit" in on
    # flag-off: the fold step (and its command) must be entirely absent
    assert "commit-base-memory" not in off
