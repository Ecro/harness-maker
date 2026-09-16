"""AC-011 (render half), AC-015 (render half), AC-019 — the rendered prose and the skill.

Both variants are rendered from this repo's own `harness.yaml` through
`tests/structural/_surface_baseline.render_surface` (the same path the ratchet measures), so
a clause that passes here passes against what ships. Mandated-call lines are matched by the
shipped call form per target — a bare `uv run` line is inert on both and must not count.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import cast

import pytest
import yaml

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_REPO = Path(__file__).parents[2]
sys.path.insert(0, str(_REPO / "tests" / "structural"))
from _surface_baseline import render_surface  # noqa: E402

MANDATED_CALL_PREFIXES = {
    "claude": ("!uv run", "!python -m", "!hm "),
    "codex": ('Bash("uv run', 'Bash("python -m', 'Bash("hm '),
}
ASK_TOKEN = {"claude": "AskUserQuestion", "codex": "request_user_input"}
VERB_ARGUMENT_FORMS = (
    "hm world assume observe <id> --relation <confirms|supersedes|contradicts> --text"
    " --observed-at",
    "hm world assume resolve <id> --status --claim",
    "hm world outcome record <id> --value --observed-at --evidence",
    "hm world objective <approve|activate|drop|reopen> <id>",
    "hm world objective close <id> --observed <met|missed|no_data> --note",
)
TRIGGER_PHRASES = ("observed", "close", "approve", "drop", "record", "where")
ORDERED_RULE = (
    "AskUserQuestion",
    "showing the exact arguments",
    "affirmative",
    "run the write once",
    "on any other answer or no answer",
    "write nothing",
)


@pytest.fixture(scope="module")
def surface() -> dict[str, dict[str, str]]:
    return cast(dict[str, dict[str, str]], render_surface())


def _command(surface: dict[str, dict[str, str]], target: str, name: str) -> str:
    return surface[target][name if target == "claude" else f"hm-{name}"]


def _mandated_lines(text: str, target: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip().startswith(MANDATED_CALL_PREFIXES[target])]


def _in_order(text: str, needles: tuple[str, ...] | list[str]) -> bool:
    pos = -1
    for n in needles:
        nxt = text.find(n, pos + 1)
        if nxt < 0:
            return False
        pos = nxt
    return True


# ── AC-011 render half ────────────────────────────────────────────────────────


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_ac_011_plan_loads_state_matches_rejected_and_loops_the_revisit_before_step_1(
    surface: dict[str, dict[str, str]], target: str
) -> None:
    plan = _command(surface, target, "plan")
    before = plan[: plan.index("Step 1 — Pre-interview")]
    lines = _mandated_lines(before, target)
    assert any("intent.yaml" in ln and "assumptions.yaml" in ln for ln in lines), lines
    assert "rejected" in before
    assert "For each matching objective:" in before
    assert any("world objective revisit <objective-id>" in ln for ln in lines), lines
    assert before.index("rejected") < before.index("For each matching objective:")
    assert before.index("For each matching objective:") < before.index(
        "world objective revisit <objective-id>"
    )


# ── AC-015 render half ────────────────────────────────────────────────────────


def _block(text: str, open_marker: str) -> str:
    start = text.index(open_marker)
    end = text.index("<!-- /@hm:answer-gated -->", start)
    return text[start:end]


@pytest.mark.parametrize("target", ["claude", "codex"])
@pytest.mark.parametrize(
    ("marker", "cmd"),
    [
        ("<!-- @hm:answer-gated:assumption -->", "hm world assume"),
        ("<!-- @hm:answer-gated:objective-close -->", "hm world objective close"),
    ],
    ids=["assumption", "objective-close"],
)
def test_ac_015_wrapup_writes_sit_inside_answer_gated_blocks_with_an_explicit_no_branch(
    surface: dict[str, dict[str, str]], target: str, marker: str, cmd: str
) -> None:
    wrapup = _command(surface, target, "wrapup")
    block = _block(wrapup, marker)
    assert _in_order(
        block, [ASK_TOKEN[target], 'If the answer is "yes":', cmd, "Otherwise: write nothing"]
    ), block


# ── AC-019 ───────────────────────────────────────────────────────────────────


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


_FRONTMATTER_BLOCK = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL | re.MULTILINE)


def _frontmatter_description(skill: str) -> str:
    """The renderer prepends its provenance block; the skill's own block follows it."""
    for block in _FRONTMATTER_BLOCK.findall(skill):
        meta = yaml.safe_load(block)
        if isinstance(meta, dict) and "description" in meta:
            return str(meta["description"])
    raise AssertionError("no description in any frontmatter block")


@pytest.mark.parametrize("target", [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX])
def test_ac_019_the_skill_renders_for_every_target(target: Target) -> None:
    files = _render_target([target])
    assert ".claude/skills/intent-layer/SKILL.md" in files
    if target == Target.CODEX:
        assert ".agents/skills/intent-layer/SKILL.md" in files


def test_ac_019_the_skill_description_and_body_carry_the_contract() -> None:
    files = _render_target([Target.CLAUDE_CODE])
    skill = files[".claude/skills/intent-layer/SKILL.md"]
    description = _frontmatter_description(skill)
    assert len(description) <= 200, len(description)
    for phrase in TRIGGER_PHRASES:
        assert phrase in description, phrase
    body = skill[skill.index("# intent-layer") :]
    for form in VERB_ARGUMENT_FORMS:
        assert form in body, form
    assert _in_order(body, ORDERED_RULE), body


def test_ac_019_help_lists_the_skill_and_no_command_was_added(
    surface: dict[str, dict[str, str]],
) -> None:
    assert "intent-layer" in _command(surface, "claude", "help")
    assert "intent-layer" in _command(surface, "codex", "help")
    frozen = json.loads(
        (_REPO / "tests" / "fixtures" / "rendered_command_names.json").read_text(encoding="utf-8")
    )
    assert sorted(surface["claude"]) == frozen["claude"]
    assert sorted(surface["codex"]) == frozen["codex"]
