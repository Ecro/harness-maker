"""SPEC S4 / AC-004 (PLAN-workflow-steps-vs-model-capability ADR-004): the 5-term inequality
ceremony is gone from every rendered interview surface, and only the locale open-ended cap
sentence remains.

Negative goldens are the section title and residue tokens from the 0.55.0 render
(`inequality_gate_block.md.j2` partial + per-stage term lists); the positive golden is the cap
sentence, which renders from `harness.yaml` independently of the deleted partial. Both presets and
both dev_modes are asserted — the ceremony sat outside every config gate, so a residue on one arm
only would be the partial-landing bug this shape exposes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import (
    DevMode,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
    interview_deep_gate_defaults,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

RESIDUE = ("5-Term Inequality Gate", "5-term", "EIG", "CLARITI")
CAP_SENTENCE = "open-ended question(s) per turn for locale"
SURFACES = ("research", "spec", "plan", "loop")
ARMS = [(p, d) for p in Preset for d in DevMode]


def _render(
    tmp: Path, preset: Preset, dev_mode: DevMode, *, depth: str | None = None
) -> dict[str, str]:
    answers = InterviewAnswers(preset=preset, dev_mode=dev_mode, targets=[Target.CLAUDE_CODE])
    if depth is not None:
        interview = {**answers.interview, "comprehension": {"depth": depth}}
        answers = answers.model_copy(update={"interview": interview})
    render(
        synthesize(ProjectProfile(), answers, preset=preset), tmp, freeze_time=DEFAULT_FREEZE_TIME
    )
    root = tmp / "commands" / "hm"
    return {s: (root / f"{s}.md").read_text(encoding="utf-8") for s in SURFACES}


@pytest.mark.parametrize(
    ("preset", "dev_mode"), ARMS, ids=[f"{p.value}-{d.value}" for p, d in ARMS]
)
def test_five_term_ceremony_absent_cap_retained(
    tmp_path: Path, preset: Preset, dev_mode: DevMode
) -> None:
    rendered = _render(tmp_path, preset, dev_mode)
    for surface, text in rendered.items():
        for token in RESIDUE:
            assert token not in text, f"{surface}: residue {token!r} survived the deletion"
        assert CAP_SENTENCE in text, f"{surface}: the open-ended cap sentence must survive"
        cap = interview_deep_gate_defaults()["open_ended_cap_by_locale"]
        expected = cap.get("en", cap["default"])
        assert f"at most `{expected}` open-ended question(s) per turn for locale `en`" in text, (
            f"{surface}: the cap value/locale must render from config, not a stale literal"
        )


def test_comprehension_block_no_longer_points_at_the_gate(tmp_path: Path) -> None:
    """`comprehension_block.md.j2` used to say 'the 5-term gate still governs which get asked'
    at eight include sites; the reworded sentence names the cap instead. The block is gated on
    `interview.comprehension.depth == 'deep'` (default `standard`), so the fixture forces it."""
    rendered = _render(tmp_path, Preset.PRODUCTION, DevMode.SPEC_DRIVEN, depth="deep")
    for surface in ("plan", "spec"):
        assert "the 5-term gate still governs which get asked" not in rendered[surface]
        assert "the open-ended cap still governs how many get asked" in rendered[surface]
