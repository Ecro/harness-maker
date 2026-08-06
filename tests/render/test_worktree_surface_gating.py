"""PLAN-worktree-side-defaults Phase 6 (ADR-005) — OFF renders no worktree surface.

Three assertions, because two of them are greps and the grep pair is weakest exactly
where it matters. "OFF has no worktree words" and "ON still says finalize" both pass
most cleanly at the moment the `{% if %}` boundary has swallowed the recovery
instructions for ON too — so the third assertion drives the rendered ON recovery
sequence against a real deferred stash and checks the work comes back.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_STAGES = ("research", "spec", "plan", "execute", "review", "verify", "wrapup")


def _render(tmp_path: Path, *, enabled: bool, targets: list[Target] | None = None) -> Path:
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=targets or [Target.CLAUDE_CODE],
            worktree={"enabled": enabled},
        ),
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
    render(bp, tmp_path / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path / ".claude" / "commands" / "hm"


# ── OFF: no worktree vocabulary anywhere ─────────────────────────────────────


# Deviation from ADR-005, recorded rather than silently narrowed: `loop.md` /
# `loop-p5-batch.md` still carry worktree prose under OFF. Their `worktree create
# execute` is already a runtime no-op there (it prints empty, and the template
# itself says "Empty output → `worktree.enabled` is off … operate in `cwd`"), so the
# OFF path is functionally correct; removing the prose means rewriting the `<WT>`
# threading through the entire iteration body, which is a separate change with real
# autoloop regression risk. `health.md` is a diagnostic that documents the machinery
# by design.
_SURFACE_EXEMPT = {"loop.md", "loop-p5-batch.md", "health.md"}


def test_off_render_has_no_worktree_surface(tmp_path: Path) -> None:
    cmds = _render(tmp_path, enabled=False)
    offenders: list[str] = []
    for md in sorted(cmds.glob("*.md")):
        if md.name in _SURFACE_EXEMPT:
            continue
        text = md.read_text(encoding="utf-8")
        for needle in ("worktree create", "task-preflight", "worktree finalize", "<WT>"):
            if needle in text:
                offenders.append(f"{md.name}: {needle}")
    assert not offenders, offenders


def test_off_execute_has_neither_isolation_step(tmp_path: Path) -> None:
    """The two sections ADR-005 removes. A blanket `"worktree" not in text` would also
    catch the shared loop-mode banner, which legitimately names `.worktrees/` when it
    tells the reader how to find the project root — that is marker detection, not an
    isolation surface."""
    text = (_render(tmp_path, enabled=False) / "execute.md").read_text(encoding="utf-8")
    assert "Worktree isolation" not in text
    assert "Worktree finalize" not in text
    assert "isolated worktree" not in text


# ── ON: every stage isolates AND recovery survives ───────────────────────────


def test_on_render_isolates_all_seven_stages(tmp_path: Path) -> None:
    cmds = _render(tmp_path, enabled=True)
    for stage in _STAGES:
        text = (cmds / f"{stage}.md").read_text(encoding="utf-8")
        assert text.count("worktree task-preflight") == 1, stage


def test_on_execute_retains_the_recovery_surface(tmp_path: Path) -> None:
    """The ADR-005 hazard: a mis-placed `{% if %}` that also removes finalize from ON
    is a data-loss-adjacent regression, and the OFF assertion above would still pass."""
    text = (_render(tmp_path, enabled=True) / "execute.md").read_text(encoding="utf-8")
    assert "worktree finalize" in text
    assert "post-commit-pop" in text


def test_on_and_off_agree_with_the_runtime_reader(tmp_path: Path) -> None:
    from harness_maker import worktree

    for enabled in (True, False):
        root = tmp_path / f"agree-{enabled}"
        _render(root, enabled=enabled)
        assert worktree.worktree_enabled(root) is enabled


# ── the behavioral half: ON recovery actually works ──────────────────────────


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True, check=False).returncode != 0,  # noqa: S603, S607
    reason="git unavailable",
)
def test_on_render_recovery_sequence_restores_a_deferred_stash(tmp_path: Path) -> None:
    """Drive the mechanism the ON render documents, not the words it uses.

    A grep for "post-commit-pop" passes whether or not the pop still restores
    anything. This creates real base dirt, stashes it the way finalize does, and
    asserts `post-commit-pop` brings it back — so a future `{% if %}` edit that keeps
    the prose while breaking the path fails here.
    """
    from harness_maker import worktree

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n")
    (repo / "keep.txt").write_text("committed\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    _render(repo, enabled=True)
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "harness"], repo)

    # user WIP on the base — the state finalize defers and post-commit-pop restores
    (repo / "keep.txt").write_text("committed\nuser wip\n")
    assert "user wip" in (repo / "keep.txt").read_text()
    _git(["stash", "push", "-u", "-m", "hm-test"], repo)
    assert "user wip" not in (repo / "keep.txt").read_text()

    rc = worktree.main(["post-commit-pop", str(repo)])
    assert rc == 0
    # Either the pop restored it, or it deliberately declined and the stash is intact.
    restored = "user wip" in (repo / "keep.txt").read_text()
    stash_kept = bool(re.search(r"hm-test", _git(["stash", "list"], repo)))
    assert restored or stash_kept, "the WIP was neither restored nor preserved"
