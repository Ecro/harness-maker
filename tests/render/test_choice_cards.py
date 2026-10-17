"""SPEC-choice-cards AC-001..004: every user choice in an hm render uses the question tool."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import yaml

from tests._overhaul_p1_ref import HEAD_SRC, init_project, run_make

PRESETS = ("Side", "Production")
STAGES = ("research", "spec", "execute", "wrapup")
TOOL = {"claude": "AskUserQuestion", "codex": "request_user_input"}
_ARGS = ("--autoloop", "--targets", "claude-code,codex", "--locale", "en")
_SPEC = Path(__file__).resolve().parents[2] / "specs" / "SPEC-choice-cards.machine.yaml"

_RULE_TAIL = (
    "; recommendation first, except approvals and equal options. Without the tool: a numbered "
    "list, then wait; never choose for the user."
)
#: SPEC AC-001, verbatim.
CHOICE_RULE = {
    "claude": "**Choices.** Ask each choice with `AskUserQuestion`" + _RULE_TAIL,
    "codex": "**Choices.** Ask each choice with `request_user_input` where available" + _RULE_TAIL,
}


def _renders_of(template: str) -> list[tuple[str, str]]:
    """(runtime, rendered path) for a template, per the targets this SPEC covers."""
    if template.startswith("stages/"):
        s = template.removeprefix("stages/").removesuffix(".md.j2")
        return [
            ("claude", f".claude/commands/hm/{s}.md"),
            ("codex", f".agents/skills/hm-{s}/SKILL.md"),
        ]
    if template == "skills/world-model/SKILL.md.j2":
        return [
            ("claude", ".claude/skills/maker/SKILL.md"),
            ("codex", ".agents/skills/maker/SKILL.md"),
        ]
    if template.startswith("commands/hm/"):
        return [("claude", ".claude/" + template.removesuffix(".j2"))]
    raise AssertionError(template)


def _sites() -> list[tuple[str, str, str]]:
    """(site, template, anchor) rows from AC-002's golden table — the SPEC is the oracle."""
    acs = yaml.safe_load(_SPEC.read_text(encoding="utf-8"))["ac"]
    rows = next(a for a in acs if a["id"] == "AC-002")["golden_table"]
    return [(r["input"]["site"], r["input"]["template"], r["expected"]) for r in rows]


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    cache: dict[str, Path] = {}

    def get(preset: str) -> Path:
        if preset not in cache:
            base = tmp_path_factory.mktemp(f"choice-{preset}")
            project = init_project(base / "proj")
            proc = run_make(project, (*_ARGS, "--preset", preset), src=HEAD_SRC, home=base / "home")
            assert proc.returncode == 0, proc.stderr[-2000:]
            cache[preset] = project
        return cache[preset]

    return get


def _rule_files() -> Iterator[tuple[str, str]]:
    for s in STAGES:
        yield from _renders_of(f"stages/{s}.md.j2")
    yield from _renders_of("skills/world-model/SKILL.md.j2")


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_001_commands_carry_the_choice_rule(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    root = rendered(preset)
    counts = {
        rel: (root / rel).read_text("utf-8").count("\n\n" + CHOICE_RULE[runtime])
        for runtime, rel in _rule_files()
    }
    assert counts == dict.fromkeys(counts, 1)


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_002_choice_sites_name_the_question_tool(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    root = rendered(preset)
    sites = _sites()
    assert len(sites) == 13
    bad = []
    for site, template, anchor in sites:
        for runtime, rel in _renders_of(template):
            text = (root / rel).read_text("utf-8")
            if anchor not in text:
                bad.append((site, rel, "anchor missing"))
                continue
            after = text[text.index(anchor) + len(anchor) :][:200].split("\n\n")[0]
            if TOOL[runtime] not in after:
                bad.append((site, rel, "no tool after anchor"))
    assert bad == []


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_003_no_render_names_cursor_askquestion(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    root = rendered(preset)
    hits = [
        p.relative_to(root).as_posix()
        for d in (".claude", ".agents")
        for p in (root / d).rglob("*")
        if p.is_file() and "AskQuestion" in p.read_text("utf-8", errors="replace")
    ]
    assert hits == []


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_004_spec_exempts_only_at_auto_full(
    preset: str, rendered: Callable[[str], Path]
) -> None:
    root = rendered(preset)
    for _, rel in _renders_of("stages/spec.md.j2"):
        text = (root / rel).read_text("utf-8")
        assert "and the DRI was not asked (`auto_full`)." in text, rel
        assert "or no question tool" not in text, rel
