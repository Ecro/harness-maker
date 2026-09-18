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
NEW_LABEL = "new — record an assumption"
ADD_CMD = "hm world assume add <id> --claim"
OBSERVE_LOCATOR = "[--locator <path:A-B>]"
OPTION_CAP = "at most two assumption ids"
CONFIRM_NEW = "show the exact `add` arguments"
GAP_SOURCE = "`hm world gap --json`"
ASK_TOKEN = {"claude": "AskUserQuestion", "codex": "request_user_input"}
MANDATED = {"claude": ("!uv run", "!python -m", "!hm "), "codex": ('Bash("uv run', 'Bash("hm ')}
SKILL_ADD_FORM = (
    "hm world assume add <id> --claim --status <known|assumed|unknown>"
    " [--text --observed-at [--locator <path:A-B>]]"
)
SKILL_OBSERVE_FORM = (
    "hm world assume observe <id> --relation <confirms|supersedes|contradicts> --text"
    " --observed-at [--claim] [--locator <path:A-B>]"
)


@pytest.fixture(scope="module")
def surface() -> dict[str, dict[str, str]]:
    return cast(dict[str, dict[str, str]], render_surface())


def _assumption_block(surface: dict[str, dict[str, str]], target: str) -> str:
    wrapup = surface[target]["wrapup" if target == "claude" else "hm-wrapup"]
    start = wrapup.index("<!-- @hm:answer-gated:assumption -->")
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
    for literal in (STALE_LABEL, NEW_LABEL, OPTION_CAP, GAP_SOURCE, "`stale_evidence`"):
        assert literal in block, literal
    assert _after(
        block, ASK_TOKEN[target], 'If the answer is "yes":', ADD_CMD, "Otherwise: write nothing"
    ), block
    # "new" is a choice to record, not approval of a record the model wrote: the arguments are
    # shown and confirmed with a second question before the one `add` call (codex dbc13952).
    assert _after(block, NEW_LABEL, CONFIRM_NEW, ASK_TOKEN[target], ADD_CMD), block
    calls = [ln for ln in block.splitlines() if ln.strip().startswith(MANDATED[target])]
    assert sum(ADD_CMD in ln for ln in calls) == 1, calls
    observe = [ln for ln in calls if "hm world assume observe" in ln]
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
