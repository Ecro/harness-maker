"""The SPEC-need block is spec-driven-only, and it reports rather than gates.

Replaces `test_render_plan_spec_need.py` (SPEC-plan-stage-absorption). That file asserted the
whole of `/hm:plan` Step 1.7 — detection, the re-entry marker (`marker-write` / `marker-read` /
`marker-fresh` / `marker-clear`), the interactive [Author now] / [Waive] branch, and
`waiver-set`. **Only part of that moved.** `/hm:execute` Step 0.1 keeps the half that produces
evidence — `prefilter` for candidates, `record` for the verdict and its rationale, and the
frontmatter write — and deliberately drops the half that *halted*: the absorption removes the
human gate between specification and implementation, so re-adding a blocking prompt here would
put back exactly what it took out. Enforcement did not disappear; it moved downstream to
`/hm:verify` Check 6, which still runs `op-check` / `waiver-check` / `waiver-set`.

`marker-*` consequently has no caller in any rendered template. That is a known orphan, filed
rather than hidden: retiring those verbs is a public-CLI change and belongs to its own task.

The dev_mode gating is what stays load-bearing here. A task-driven harness must not carry one
byte of this block — it is the "byte-unchanged path for task-driven users" contract the
original file existed to hold, and that contract survived the move intact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import DevMode, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _execute(tmp_path: Path, dev_mode: DevMode, target: Target = Target.CLAUDE_CODE) -> str:
    """Render a full harness and return the execute stage command body."""
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[target],
            dev_mode=dev_mode,
        ),
    )
    render(bp, tmp_path / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    pattern = "hm-execute/SKILL.md" if target == Target.CODEX else "commands/hm/execute.md"
    files = list(tmp_path.rglob(pattern))
    assert files, "execute.md command file not found in rendered output"
    return files[0].read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def task_driven(tmp_path_factory: pytest.TempPathFactory) -> str:
    return _execute(tmp_path_factory.mktemp("task"), DevMode.TASK_DRIVEN)


@pytest.fixture(scope="module")
def spec_driven(tmp_path_factory: pytest.TempPathFactory) -> str:
    return _execute(tmp_path_factory.mktemp("spec"), DevMode.SPEC_DRIVEN)


# ── (a) task-driven: the whole block is ABSENT ───────────────────────────────


def test_task_driven_omits_the_step_0_1_heading(task_driven: str) -> None:
    assert "Step 0.1" not in task_driven, (
        "task-driven execute.md must NOT contain Step 0.1 — SPEC-need is spec-driven-only"
    )


def test_task_driven_omits_every_spec_need_call(task_driven: str) -> None:
    assert "spec_need" not in task_driven, (
        "task-driven execute.md must not reference the spec_need CLI at all; a single leaked "
        "call is a task-driven user being asked to run a spec-driven gate"
    )


def test_task_driven_frontmatter_omits_the_verdict_keys(task_driven: str) -> None:
    for key in ("spec_need_verdict", "spec_need_target"):
        assert key not in task_driven, f"task-driven PLAN frontmatter must not declare {key}"


# ── (b) spec-driven: evidence, then the write ────────────────────────────────


def test_spec_driven_includes_the_step_0_1_heading(spec_driven: str) -> None:
    assert "Step 0.1" in spec_driven


def test_spec_driven_gathers_candidates_before_judging(spec_driven: str) -> None:
    """`prefilter` is a hint the model judges — but it has to be asked for."""
    assert "spec_need prefilter" in spec_driven
    assert spec_driven.index("spec_need prefilter") < spec_driven.index("spec_need record"), (
        "the verdict is recorded before the candidates are fetched, so the recorded rationale "
        "cannot have been informed by them"
    )


def test_spec_driven_records_the_verdict_with_a_rationale(spec_driven: str) -> None:
    assert "spec_need record" in spec_driven
    assert "--rationale" in spec_driven, (
        "a verdict recorded without a rationale cannot be audited later, which is the only "
        "reason this step survived the gate's removal"
    )


def test_spec_driven_writes_through_the_preserving_verb(spec_driven: str) -> None:
    assert "spec_need frontmatter-upsert" in spec_driven
    assert spec_driven.index("spec_need record") < spec_driven.index(
        "spec_need frontmatter-upsert"
    ), "the frontmatter is written before the verdict is recorded"


def test_spec_driven_asserts_the_key_is_present_after_the_write(spec_driven: str) -> None:
    """The absent case is the whole failure mode — Check 6 reads an absent key as PASS."""
    after_write = spec_driven.split("spec_need frontmatter-upsert", 1)[1]
    guard = " ".join(after_write.split("#### Step 0.2", 1)[0].lower().split())
    readback = guard.index("read the frontmatter back")
    absent = guard.index("if `spec_need_verdict` is absent", readback)
    retry = guard.index("retry the call once", absent)
    terminal = guard.index("if it is still absent", retry)
    assert "surface the path and the error and stop" in guard[terminal:]


@pytest.mark.parametrize("target", [Target.CLAUDE_CODE, Target.CODEX])
def test_execute_inputs_allow_step_zero_to_author_missing_plan(
    tmp_path: Path, target: Target
) -> None:
    text = _execute(tmp_path, DevMode.SPEC_DRIVEN, target)
    inputs = text.split("## Inputs", 1)[1].split("## Session Context Loading", 1)[0]
    plan_input = next(line for line in inputs.splitlines() if "PLAN-{slug}.md" in line)
    assert "reuse" in plan_input
    assert "Step 0 creates it if absent" in plan_input
    assert "error if missing" not in plan_input


# ── (c) the gate is gone, and that is asserted, not assumed ──────────────────


def test_the_block_never_halts(spec_driven: str) -> None:
    """The DRI kept the evidence and dropped the gate. Assert the gate stayed dropped.

    Negative invariant. It is green now because no halting construct was ported, and it goes
    red the moment one is re-added — which is the change the absorption exists to prevent.
    """
    window = spec_driven[spec_driven.index("Step 0.1") :][:4000]
    for banned in ("AskUserQuestion", "[Author now]", "STOP this invocation", "marker-write"):
        assert banned not in window, (
            f"Step 0.1 contains `{banned}` — the SPEC-need block halted in /hm:plan and must "
            "not halt here; enforcement is /hm:verify Check 6's job"
        )
