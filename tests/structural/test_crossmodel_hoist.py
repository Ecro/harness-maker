"""AC-009 of SPEC-workflow-loop-efficiency — cross-model voters launch with Pass 1.

⚠️ Name collision, on purpose-avoidance grounds: `tests/render/test_render_review_read_
budget.py` also has an "AC-009". That one belongs to the read-budget SPEC and is an
invariance guard. This one is the ADR-011 hoist. Same id, different SPEC.

ADR-011: nothing in the cross-model path consumes Pass 1 or Pass 2 output — each model's
input is the diff — so waiting for Pass 2 to finish before launching them was a pure
serialization barrier. The findings join at the Step 4 fold either way.

What this file proves is ORDERING IN THE RENDERED TEXT, not runtime concurrency. A
render-grep cannot observe whether the model actually launches them early (CLAUDE.md
checkpoint 2). It proves the instruction is present and positioned ahead of Pass 2.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from tempfile import mkdtemp
from typing import Literal

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, SecondOpinionConfig, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_LOOP_HEADING = "## Auto-Fix Loop"

_HOIST = re.compile(r"Launch the cross-model voters NOW, concurrently with Pass 1")
_PASS2 = re.compile(r"^####\s*Pass\s*2\b", re.MULTILINE)
# Step 3.6, NOT 3.7. The template's own prose said "Step 3.6/3.7 (PIDA)" and this test
# was written against 3.7 — there is no such heading, and never was. Both the prose and
# CLAUDE.md carried the stale number; the prose is corrected, CLAUDE.md is out of this
# PLAN's scope and is recorded for wrapup.
_PIDA = re.compile(r"^###\s*Step\s*3\.6\b", re.MULTILINE)


def _offset(pattern: re.Pattern[str], text: str) -> int | None:
    m = pattern.search(text)
    return None if m is None else m.start()


def _render(*, models: list[Literal["codex", "antigravity"]]) -> Path:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    answers.second_opinion = SecondOpinionConfig(models=models)
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-hoist-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


def _review_bearing(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): text
        for path in sorted(root.rglob("*.md"))
        if _LOOP_HEADING in (text := path.read_text(encoding="utf-8"))
    }


@cache
def render_all_targets() -> dict[str, str]:
    return _review_bearing(_render(models=["codex", "antigravity"]))


@cache
def _render_second_opinion_off() -> dict[str, str]:
    return _review_bearing(_render(models=[]))


def crossmodel_launch_offset(text: str) -> int:
    """AC-009 free symbol — the hoist offset WITHIN one artifact.

    Takes a single document, not the corpus. An earlier draft took the corpus and folded
    it with `max`, comparing character offsets across documents of different lengths;
    that is not an ordering relation, and it went red against a render where every
    artifact was correctly ordered. The corpus-level quantifier lives in the predicate.
    """
    off = _offset(_HOIST, text)
    assert off is not None, "a review-bearing artifact has no hoist block"
    return off


def pass2_offset(text: str) -> int:
    off = _offset(_PASS2, text)
    assert off is not None, "a review-bearing artifact has no Pass 2 heading"
    return off


def test_the_corpus_covers_all_three_artifact_families() -> None:
    """Positive control — every offset comparison below is vacuous over an empty corpus."""
    found = render_all_targets()
    assert ".claude/commands/hm/review.md" in found
    assert ".claude/stages/review.md" in found
    assert ".agents/skills/hm-review/SKILL.md" in found


def test_ac_009_crossmodel_launches_with_pass1() -> None:
    """AC-009's executable predicate, verbatim."""
    assert all(crossmodel_launch_offset(t) < pass2_offset(t) for t in render_all_targets().values())


def test_the_predicate_names_the_offending_artifact() -> None:
    """Same relation as the AC, but per-artifact so a failure is diagnosable.

    `all(...)` reports only False. The AC test is kept verbatim for the binding; this is
    the one that says WHICH surface regressed.
    """
    for name, text in render_all_targets().items():
        hoist, pass2 = crossmodel_launch_offset(text), pass2_offset(text)
        assert hoist < pass2, f"{name}: hoist at {hoist} is not ahead of Pass 2 at {pass2}"


def test_pida_still_follows_the_voters() -> None:
    """The scope guard. PIDA genuinely consumes cross-model findings — it must NOT hoist.

    Without this, "move the cross-model work earlier" is satisfiable by dragging the
    acceptance gate up with it, which would adjudicate findings that do not exist yet.
    """
    for name, text in render_all_targets().items():
        pida = _offset(_PIDA, text)
        assert pida is not None, f"{name}: Step 3.6 (PIDA) is missing"
        assert crossmodel_launch_offset(text) < pida, f"{name}: PIDA is not after the voters"


def test_the_hoist_is_gated_on_second_opinion_being_enabled() -> None:
    """Anti-tautology + correctness: a harness with no models must not carry the block.

    It would instruct the model to go run a step whose own preset gate then skips it —
    the dangling-pointer shape this repo has shipped before with `second-opinion-gate`.
    """
    off = _render_second_opinion_off()
    assert off, "the second-opinion-off render produced no review-bearing artifact"
    for name, text in off.items():
        assert _offset(_HOIST, text) is None, f"{name}: hoist rendered with no models enabled"


@pytest.mark.parametrize("family", [".claude/commands/hm/review.md", ".claude/stages/review.md"])
def test_the_hoist_names_step_3_5_as_its_destination(family: str) -> None:
    """A "launch them now" instruction with no destination is not actionable."""
    text = render_all_targets()[family]
    hoist = _offset(_HOIST, text)
    assert hoist is not None
    assert "Step 3.5" in text[hoist : hoist + 1200]
