"""Phase B3 render surface — the split gate, per file, and the five templates that must not move.

`stage_end_summary.md.j2` is ONE shared include under StrictUndefined. Its judgment branch is
derived from `summary_stage` rather than set by the caller precisely so the five stage templates
outside B3's scope keep rendering — so the load-bearing assertion here is not "plan has the
branch" but "research/spec/execute/verify/wrapup still do not, and still render at all".

The ADR-010 assertion is stated in the negative on purpose: the grade predicate must NOT be
level-conditional. A positive grep ("the string is present") passes just as happily when the
string has been moved inside an `auto_full` branch, which is the one change ADR-010 forbids.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.autopilot_caps import _JUDGMENT_GATED_STAGES
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_ALL_STAGES = ("research", "spec", "plan", "execute", "review", "verify", "wrapup")


@pytest.fixture(scope="module")
def commands(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("judgment-gate")
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
    )
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root / ".claude" / "commands" / "hm"


def _text(commands: Path, stage: str) -> str:
    return (commands / f"{stage}.md").read_text(encoding="utf-8")


def test_exactly_the_judgment_stages_carry_the_flag(commands: Path) -> None:
    carrying = {s for s in _ALL_STAGES if "--judgment-gate" in _text(commands, s)}
    assert carrying == set(_JUDGMENT_GATED_STAGES), (
        "the rendered surface and autopilot_caps._JUDGMENT_GATED_STAGES disagree about which "
        f"stages own a judgment gate: rendered={sorted(carrying)}, "
        f"code={sorted(_JUDGMENT_GATED_STAGES)}"
    )


@pytest.mark.parametrize("stage", sorted(set(_ALL_STAGES) - set(_JUDGMENT_GATED_STAGES)))
def test_the_other_stages_keep_gate_first(commands: Path, stage: str) -> None:
    """The out-of-scope five. A shared include is easy to change for everyone by accident."""
    text = _text(commands, stage)
    assert "autopilot_caps gate-blocked" in text, f"{stage} lost its gate-first step"
    # Named tokens, not the bare word: `judgment` also appears in the machine-SPEC AC-type
    # prose (`type: judgment`) that four of these five carry, and matching that reported a
    # branch nobody had added.
    for token in ("--judgment-gate", "judgment_gate"):
        assert token not in text, f"{stage} gained a judgment branch it does not own ({token})"


@pytest.mark.parametrize("stage", sorted(_JUDGMENT_GATED_STAGES))
def test_the_judgment_stages_do_not_stop_at_step_1(commands: Path, stage: str) -> None:
    text = _text(commands, stage)
    assert "--judgment-gate" in text
    assert "judgment_gate" in text, f"{stage} does not explain the halt kind it can receive"


def test_the_review_grade_predicate_is_not_level_conditional(commands: Path) -> None:
    """ADR-010's hard half: a failed grade stops at auto_full too."""
    text = _text(commands, "review")
    assert "CHANGES_REQUESTED" in text
    assert "halts at EVERY level" in text, (
        "the grade predicate must state that no level clears it — if it moved inside a "
        "level-conditional branch, this PLAN reversed a recorded invariant"
    )
    # The REVIEW-SPECIFIC sentence, not the bare flag name. The shared partial lists all
    # three values and renders into plan.md too, so `"--judgment-gate blocked" in text` was
    # satisfied by prose that says nothing about the grade — a test passing for the wrong
    # reason, which is worse than none.
    assert "CHANGES_REQUESTED (grade < threshold) → pass --judgment-gate blocked" in text, (
        "the grade half must be carried by the flag value the CODE refuses to clear, and "
        "review's own gate string must be what names it; a sentence saying 'stop at every "
        "level' with no mechanism behind it is the prose-only enforcement Interview #5 rejected"
    )


def test_the_review_judgment_half_routes_to_the_boundary(commands: Path) -> None:
    text = _text(commands, "review")
    assert "human_review_needed" in text
    assert "passed-over finding ids" in text, (
        "auto_full's compensating control for the only provenance exception in this harness "
        "is the recorded id list; without it the clearance is unauditable"
    )


def test_plan_records_its_auto_answer(commands: Path) -> None:
    assert "Interview Transcript" in _text(commands, "plan")


def test_the_plan_threshold_half_is_named_by_plans_own_gate(commands: Path) -> None:
    """The mirror of the review assertion, and for the same reason.

    plan's gate string mapped *every* unresolved round to `pending`, so a plan the validator
    twice called critically flawed was auto-answered at `auto_full` — the plan-stage analogue
    of the review P0. Assert the plan-SPECIFIC sentence: the shared partial lists all three
    values in every stage, so a bare `"blocked" in text` passes with this sentence deleted.
    """
    text = _text(commands, "plan")
    assert "MAJOR_REVISION on its SECOND pass" in text
    assert "No level clears it, auto_full included" in text
