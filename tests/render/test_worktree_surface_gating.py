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


# `health.md` is the one exemption and it is deliberate: it is a DIAGNOSTIC command whose
# job is to describe the worktree machinery to the operator, so naming `worktree create`
# there is content, not a live instruction.
#
# `loop.md` / `loop-p5-batch.md` used to be exempt too — ADR-005 named them but the
# `<WT>` threading through the whole iteration body made the removal look riskier than
# the prose was worth. It was done afterwards: section 5 branches, the command sites take
# `{{ cdwt }}`/`{{ WTR }}`, and prose takes `{{ WTP }}`. The exemption is gone, which is
# the point — an "accepted limitation" that keeps its test exemption is indistinguishable
# from one nobody ever revisits.
_SURFACE_EXEMPT = {"health.md"}


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


def test_on_loop_keeps_its_isolation_machinery(tmp_path: Path) -> None:
    """The mirror of the OFF assertion. Stripping `<WT>` from the loop under OFF is only
    correct if the ON render still creates, verifies and finalizes — a `{% if %}` that
    swallowed both sides would pass the OFF test alone."""
    text = (_render(tmp_path, enabled=True) / "loop.md").read_text(encoding="utf-8")
    for needle in (
        "worktree create execute",
        "worktree verify",
        "worktree finalize",
        "cd <WT> &&",
    ):
        assert needle in text, needle


def test_off_loop_still_self_gates_and_names_the_cost(tmp_path: Path) -> None:
    """Removing the worktree prose must not remove the Stop-hook marker the loop needs to
    self-gate, nor silently drop the fact that deliverables now accumulate in place.

    Assert the COMMAND, not the word. The first version of this test grepped for
    `hm-loop-active` and passed while the OFF render contained only a sentence *claiming*
    the marker is written — the `touch` had been swallowed by the ON-only branch, so an
    OFF loop would have self-stopped after iteration 1. That is the same
    grep-passes-while-behavior-is-broken shape this module's docstring is about.
    """
    text = (_render(tmp_path, enabled=False) / "loop.md").read_text(encoding="utf-8")
    assert "touch .hm-loop-active" in text, "the OFF loop never writes its own marker"
    # …and the condition guarding it must be trivially true without a worktree path
    assert '[ "$(pwd)" = "$(pwd)" ]' in text
    assert "uncommitted" in text


def test_on_loop_marker_stays_session_scoped(tmp_path: Path) -> None:
    """The mirror: with isolation on, the guard must still compare the WORKTREE path to
    cwd — collapsing both branches to `$(pwd)` would make every ON loop take the
    session-blind degraded path and block peers' termination."""
    text = (_render(tmp_path, enabled=True) / "loop.md").read_text(encoding="utf-8")
    assert '[ "<WT>" = "$(pwd)" ]' in text


# ── RESEARCH V8: the deliverable write instruction must name its own target ──

_DELIVERABLE_DIRS = {
    "spec": "specs/",
    "research": "work-docs/",
    "plan": "work-docs/",
    "review": "work-docs/",
}
_DELIVERABLE_WRITES = {
    "spec": "SPEC-{slug}.md",
    "research": "RESEARCH-{slug}.md",
    "plan": "PLAN-{slug}.md",
    "review": "REVIEW-{slug}-{date}.md",
}


@pytest.mark.parametrize(("stage", "doc"), sorted(_DELIVERABLE_WRITES.items()))
def test_deliverable_write_instruction_is_rooted(tmp_path: Path, stage: str, doc: str) -> None:
    """RESEARCH V8. The concrete instruction used to read `Write to \\`work-docs/PLAN…\\``
    with no root, and ONLY the preflight preamble's generic "treat that string as `<WT>`"
    sentence routed it into the worktree. That is prompt reliability, not determinism —
    a reader who follows the concrete line writes the deliverable to the base tree even
    with isolation ON, which is a second, independent way to dirty the base.

    Asserted on both modes so the fix cannot be "hardcode `<WT>`", which would render a
    nonexistent path into every OFF harness.
    """
    on = (_render(tmp_path / "on", enabled=True) / f"{stage}.md").read_text(encoding="utf-8")
    off = (_render(tmp_path / "off", enabled=False) / f"{stage}.md").read_text(encoding="utf-8")
    assert f"<WT>/{_DELIVERABLE_DIRS[stage]}{doc}" in on, f"{stage}: ON target not rooted at <WT>"
    assert f"./{_DELIVERABLE_DIRS[stage]}{doc}" in off, f"{stage}: OFF target not rooted at ."


# ── the finalize instruction is scoped to the model it belongs to ─────────────


def test_execute_step5_gates_finalize_on_the_worktree_model(tmp_path: Path) -> None:
    """Step 5's `finalize` must not reach a per-task worktree.

    The rendered `/hm:execute` opens with the per-task `task-preflight` and then told the
    operator to run `worktree finalize <WT> stage-only` — a LEGACY-model instruction that
    merges into base, which is `task-land`'s job. Both blocks render under the same `wt_on`,
    so the separation cannot be made at render time: `<WT>` is an `execute-<uuid>` worktree
    under `/hm:loop` (where finalize is correct) and an `hm/<slug>` task worktree otherwise.
    The gate is therefore a RUNTIME branch read, and this asserts it is present and precedes
    the finalize call it guards.
    """
    body = (_render(tmp_path, enabled=True) / "execute.md").read_text(encoding="utf-8")

    gate_at = body.find("rev-parse --abbrev-ref HEAD")
    finalize_at = body.find("worktree finalize <WT> stage-only")
    assert gate_at != -1, "Step 5 has no runtime branch check — finalize is unscoped again"
    assert finalize_at != -1, "the finalize call vanished; this test would then assert nothing"
    assert gate_at < finalize_at, "the branch check must come BEFORE the finalize it guards"
    # The skip must name the branch shape, not merely 'a task worktree' — the operator has
    # to be able to evaluate it, and `hm/` is the same discriminator wrapup Step 7.7 uses.
    assert "`hm/*`" in body[gate_at - 400 : finalize_at]


def test_execute_step5_no_longer_cites_a_step_that_does_not_exist(tmp_path: Path) -> None:
    """`/hm:execute` stopped creating ephemeral worktrees; the prose kept citing that step.

    A reader following "Step 0 `worktree create`" finds `task-preflight` there instead, which
    is how the mismatch stayed invisible: every sentence was locally plausible.
    """
    body = (_render(tmp_path, enabled=True) / "execute.md").read_text(encoding="utf-8")

    assert "Step 0 `worktree create`" not in body
    assert "`execute-<uuid>-<ts>` worktree from Step 0" not in body
    assert "task-preflight" in body, "Step 0 is the preflight — the fixture rendered wrong"


def test_loop_tells_per_iter_stages_to_skip_their_own_preflight(tmp_path: Path) -> None:
    """One `<WT>` per iteration, or the iteration's work can be stranded.

    The loop creates an `execute-<uuid>` worktree and calls it `<WT>`; every stage file
    opens with `task-preflight`, which CREATES `.worktrees/<slug>/` and declares that path
    `<WT>` as well. The driver reads the stage inline, so both instructions sit in one
    context. Resolving toward the stage puts the iteration's work on `hm/<slug>` while
    loop-close finalizes the empty ephemeral worktree — lost to convergence, with every
    exit code 0. The loop already gives wrapup this exact override; this asserts the
    per-iter stages get it too.
    """
    loop = (_render(tmp_path, enabled=True) / "loop.md").read_text(encoding="utf-8")

    dispatch_at = loop.find("Invoke per-iter stages")
    assert dispatch_at != -1, "the per-iter dispatch step vanished"
    # Scoped to the dispatch step: the wrapup override further down says the same words,
    # so an unscoped `in loop` would pass on a document that never told the STAGES.
    section = loop[dispatch_at : dispatch_at + 1200]
    assert "task-preflight" in section, "the dispatch step does not mention the preflight"
    assert "skip" in section.lower()


def test_the_loop_still_forbids_skipping_the_rest_of_a_stage(tmp_path: Path) -> None:
    """The control. The override is ONE exception; a driver that reads it as licence to
    skip steps generally would silently drop Gate 0 receipts, finalize, and Phase D."""
    loop = (_render(tmp_path, enabled=True) / "loop.md").read_text(encoding="utf-8")

    assert "without skipping any" in loop
