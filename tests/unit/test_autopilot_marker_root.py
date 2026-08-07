"""ADR-003 — autopilot marker root resolution across worktree boundaries.

The marker is owned by the base repo root, but `/hm:` stages run inside
`.worktrees/<slug>/`. `resolve_marker_root` must map any worktree cwd back to the
base so read/write/clear all agree — including the WRITE-first-arm (no marker yet),
which the old existence-gated resolver got wrong (plan-validator CRITICAL).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from harness_maker import autopilot
from harness_maker.models import AtomicStage

_PIPE = [AtomicStage("research"), AtomicStage("plan")]


def _make_project(tmp_path: Path) -> Path:
    """A base repo root carries a harness sentinel."""
    base = tmp_path / "proj"
    (base / ".claude").mkdir(parents=True)
    (base / ".claude" / "harness.yaml").write_text("autonomy:\n  level: auto_safe\n")
    return base


def _worktree(base: Path, slug: str) -> Path:
    wt = base / ".worktrees" / slug
    wt.mkdir(parents=True)
    # a git worktree carries a `.git` FILE — proves the strip must run before the walk
    (wt / ".git").write_text("gitdir: /somewhere\n")
    return wt


def test_resolve_base_is_identity(tmp_path: Path) -> None:
    base = _make_project(tmp_path)
    assert autopilot.resolve_marker_root(base) == base


def test_resolve_worktree_strips_to_base(tmp_path: Path) -> None:
    base = _make_project(tmp_path)
    wt = _worktree(base, "myslug")
    assert autopilot.resolve_marker_root(wt) == base


def test_resolve_standalone_without_sentinel_returns_start(tmp_path: Path) -> None:
    # No `.claude/harness.yaml`, no `.git` anywhere up-tree → unchanged (existing
    # tests pass bare tmp_path and must keep resolving to themselves).
    lonely = tmp_path / "nowhere"
    lonely.mkdir()
    assert autopilot.resolve_marker_root(lonely) == lonely


def test_resolve_ordinary_worktrees_dir_not_misresolved(tmp_path: Path) -> None:
    # A real project whose path merely CONTAINS `.worktrees` as an ordinary dir,
    # with NO sentinel at the strip base → must fall through to the real project,
    # not the bare parent (Codex MED-3 sentinel guard).
    outer = tmp_path / "outer"  # NOT a project root (no sentinel)
    real = outer / ".worktrees" / "data"
    (real / ".claude").mkdir(parents=True)
    (real / ".claude" / "harness.yaml").write_text("x: 1\n")
    assert autopilot.resolve_marker_root(real) == real


def test_write_from_worktree_lands_at_base(tmp_path: Path) -> None:
    # The plan-validator CRITICAL: write-first-arm from a worktree (no marker yet)
    # must resolve to base, NOT write a worktree-local marker.
    base = _make_project(tmp_path)
    wt = _worktree(base, "myslug")
    now = datetime.now(UTC).isoformat()
    autopilot.write(wt, level="auto_safe", pipeline=_PIPE, now=now)
    assert autopilot.marker_path(base, session_id=None).exists(), (
        "marker must be written at the base root"
    )
    assert not autopilot.marker_path(wt, session_id=None).exists(), (
        "no worktree-local marker may be written"
    )


def test_read_from_worktree_finds_base_marker(tmp_path: Path) -> None:
    base = _make_project(tmp_path)
    wt = _worktree(base, "myslug")
    now = datetime.now(UTC)
    autopilot.write(wt, level="auto_safe", pipeline=_PIPE, now=now.isoformat())
    # Reading from inside the worktree resolves to base; the project-scoped uuid
    # matches (both keyed to base), so the marker is NOT foreign-rejected.
    marker = autopilot.active_marker(wt, now=now)
    assert marker is not None
    assert marker.level == "auto_safe"


def test_clear_from_worktree_removes_base_marker(tmp_path: Path) -> None:
    # Codex HIGH-2: `off`/clear from a worktree must delete the ROOT marker.
    base = _make_project(tmp_path)
    wt = _worktree(base, "myslug")
    autopilot.write(
        base,
        level="auto_safe",
        pipeline=[AtomicStage("research")],
        now=datetime.now(UTC).isoformat(),
    )
    assert autopilot.marker_path(base, session_id=None).exists()
    autopilot.clear(wt, session_id=None)
    assert not autopilot.marker_path(base, session_id=None).exists(), (
        "clear from worktree must remove the base marker"
    )


def test_strip_base_under_parent_git_repo_resolves_to_real_project(tmp_path: Path) -> None:
    # REVIEW P2 (security + codex): a harness project living at `<gitrepo>/.worktrees/proj`
    # must NOT have its marker captured by the parent git repo. The strip-base requires
    # `.claude/harness.yaml` (strict), so the parent's bare `.git` cannot qualify; the walk
    # then finds the real project.
    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / ".git").write_text("")  # a bare git repo, NO harness.yaml
    proj = outer / ".worktrees" / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "harness.yaml").write_text("autonomy:\n  level: auto_safe\n")
    assert autopilot.resolve_marker_root(proj) == proj


def test_boundary_marker_and_ledger_share_base_root(tmp_path: Path) -> None:
    # REVIEW P2 (code-reviewer): the boundary's marker resolves to base, so its ledger
    # 'advanced' event MUST also land at base — not the worktree ledger that gets torn
    # down with the worktree.
    from harness_maker import autopilot_caps, autopilot_ledger

    base = _make_project(tmp_path)
    wt = _worktree(base, "myslug")
    autopilot.write(base, level="auto_safe", pipeline=_PIPE, now=datetime.now(UTC).isoformat())
    rc = autopilot_caps.main(["boundary", "--root", str(wt), "--current", "research"])
    assert rc == 0
    assert autopilot_ledger.ledger_path(base).exists(), "advanced event must land in base ledger"
    assert not (wt / ".claude" / "observability").exists(), (
        "no worktree-local ledger may be written"
    )
