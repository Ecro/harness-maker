"""The round-state skill cannot be disabled out from under an unguarded pointer.

PLAN-review-round-inflation ADR-005. `review.md.j2` points at
`second-opinion-gate` §5 from a line that renders in EVERY harness, including
`second_opinion.models: []`. §5 owns the auto-fix loop's round order, the
two-arm batch trigger, the monotonic-progress rule and merge-by-`id` — the
contract that makes the loop terminate. Both presets force-enable the skill
(`interview.py`), but `skills.enabled` is user-editable, so the render is the
last place that can notice a harness whose pointer aims at a document it will
never load.

The guard auto-adds and advises rather than aborting: a hard raise would turn
`/harness-maker:make --update` into a total render failure for anyone who had
trimmed that skill, with no migration path (CLAUDE.md checkpoint #1).
"""

from __future__ import annotations

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.synthesize import ROUND_STATE_SKILL, synthesize


def _answers_without_the_skill():
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.skills["enabled"] = [s for s in answers.skills["enabled"] if s != ROUND_STATE_SKILL]
    return profile, answers


def test_a_harness_that_disabled_the_skill_gets_it_back() -> None:
    profile, answers = _answers_without_the_skill()
    assert ROUND_STATE_SKILL not in answers.skills["enabled"]  # precondition

    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)

    enabled = _rendered_enabled_skills(bp)
    assert ROUND_STATE_SKILL in enabled, (
        "the unguarded §5 pointer would aim at a skill this harness never loads"
    )


def test_the_guard_advises_rather_than_aborting(caplog: pytest.LogCaptureFixture) -> None:
    profile, answers = _answers_without_the_skill()
    with caplog.at_level("WARNING"):
        synthesize(profile, answers, preset=Preset.PRODUCTION)
    assert any(ROUND_STATE_SKILL in r.message for r in caplog.records), (
        "auto-adding silently is the same silent-degradation this guard exists to remove"
    )


def test_the_guard_is_a_no_op_when_the_skill_is_already_enabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No advisory on the normal path — a warning every render trains people to ignore it."""
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    assert ROUND_STATE_SKILL in answers.skills["enabled"]

    with caplog.at_level("WARNING"):
        bp = synthesize(profile, answers, preset=Preset.PRODUCTION)

    assert _rendered_enabled_skills(bp).count(ROUND_STATE_SKILL) == 1
    assert not any(ROUND_STATE_SKILL in r.message for r in caplog.records)


def _rendered_enabled_skills(bp: object) -> list[str]:
    """Pull the enabled list out of whichever file spec carries the skills context."""
    for spec in bp.files:  # type: ignore[attr-defined]
        ctx = getattr(spec, "context", None) or {}
        skills = ctx.get("skills")
        if isinstance(skills, dict) and "enabled" in skills:
            return list(skills["enabled"])
    pytest.fail("no rendered file carries a skills.enabled context")
