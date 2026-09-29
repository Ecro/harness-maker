"""AC-010, AC-011 (SPEC-assumption-entry-and-evidence-locator) — wrapup 5.7 and the skill.

The literals below are fixed by SPEC S8 / PLAN ADR-005 and were written into this file before
the template edit (validator critique: a label copied from the template is a circular oracle).
Both variants render through `tests/structural/_surface_baseline.render_surface`, the path the
surface ratchet measures, so a clause that passes here passes against what ships.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import cast

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_REPO = Path(__file__).parents[2]
sys.path.insert(0, str(_REPO / "tests" / "structural"))
from _surface_baseline import render_surface  # noqa: E402

STALE_LABEL = "(cited code changed)"
ADD_CMD = "hm intent question add <id> --claim"
OBSERVE_LOCATOR = "[--locator <path:A-B>]"
GAP_SOURCE = "`hm intent status --json`"
ASK_TOKEN = {"claude": "AskUserQuestion", "codex": "request_user_input"}
MANDATED = {"claude": ("!uv run", "!python -m", "!hm "), "codex": ('Bash("uv run', 'Bash("hm ')}
SKILL_ADD_FORM = (
    "hm intent question add <id> --claim-file --status <open|confirmed|wrong>"
    " [--text-file --observed-at [--locator <path:A-B>]]"
)
SKILL_OBSERVE_FORM = (
    "hm intent question observe <id> --relation <confirms|supersedes|contradicts> --text-file"
    " [--observed-at] [--claim-file] [--locator <path:A-B>]"
)


@pytest.fixture(scope="module")
def surface() -> dict[str, dict[str, str]]:
    return cast(dict[str, dict[str, str]], render_surface())


def _assumption_block(surface: dict[str, dict[str, str]], target: str) -> str:
    wrapup = surface[target]["wrapup" if target == "claude" else "hm-wrapup"]
    start = wrapup.index("<!-- @hm:answer-gated:record-batch -->")
    return wrapup[start : wrapup.index("<!-- /@hm:answer-gated -->", start)]


def _after(text: str, *needles: str) -> bool:
    pos = -1
    for needle in needles:
        pos = text.find(needle, pos + 1)
        if pos < 0:
            return False
    return True


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_ac_010_wrapup_offers_add_and_lists_stale_first(
    surface: dict[str, dict[str, str]], target: str
) -> None:
    block = _assumption_block(surface, target)
    # SPEC-intent-layer-improvements: the record batch replaced the per-question ask. Stale
    # questions still lead the list; "new" is no longer an option (new questions arrive as
    # pending rows), and selecting an item that shows its exact arguments is the confirmation,
    # so the old second question and the two-id cap are retired with it.
    for literal in (STALE_LABEL, GAP_SOURCE, "`stale_evidence`"):
        assert literal in block, literal
    ask = {"claude": "AskUserQuestion", "codex": "numbered list"}[target]
    assert _after(block, "`stale_evidence`", ADD_CMD, ask, "`declined`"), block
    calls = [ln for ln in block.splitlines() if ln.strip().startswith(MANDATED[target])]
    assert sum(ADD_CMD in ln for ln in calls) == 1, calls
    observe = [ln for ln in calls if "hm intent question observe" in ln]
    assert len(observe) == 1, calls
    assert OBSERVE_LOCATOR in observe[0], calls


def _render(target: Target) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(), InterviewAnswers(preset=Preset.PRODUCTION, targets=[target])
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        return {
            str(p.relative_to(root)): p.read_text(encoding="utf-8")
            for p in root.rglob("*")
            if p.is_file()
        }


@pytest.mark.parametrize(
    ("target", "path"),
    [
        (Target.CLAUDE_CODE, ".claude/skills/intent-layer/SKILL.md"),
        (Target.CODEX, ".agents/skills/intent-layer/SKILL.md"),
    ],
    ids=["claude", "codex"],
)
def test_ac_011_skill_lists_add_and_locator(target: Target, path: str) -> None:
    skill = _render(target)[path]
    assert SKILL_ADD_FORM in skill
    assert SKILL_OBSERVE_FORM in skill
    assert skill.count("\n") <= 120
