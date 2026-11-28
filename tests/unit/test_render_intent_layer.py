"""AC-019 — the intent-layer skill renders for every target.

The skill's contract (verbs, the three ask moments) moved to SPEC-intent-lean and is pinned in
`tests/unit/test_intent_lean.py`; the gap-proposal, measure-first and approve/drop prose this file
used to pin were retired with it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render_target(targets: list[Target]) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(), InterviewAnswers(preset=Preset.PRODUCTION, targets=targets)
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        return {
            str(p.relative_to(root)): p.read_text(encoding="utf-8")
            for p in root.rglob("*")
            if p.is_file()
        }


@pytest.mark.parametrize("target", [Target.CLAUDE_CODE, Target.CODEX])
def test_ac_019_the_skill_renders_for_every_target(target: Target) -> None:
    files = _render_target([target])
    assert ".claude/skills/intent-layer/SKILL.md" in files
    if target == Target.CODEX:
        assert ".agents/skills/intent-layer/SKILL.md" in files
