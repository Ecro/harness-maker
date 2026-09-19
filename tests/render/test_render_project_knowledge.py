"""AC-004..007 (SPEC-mission-context-loop) — the capture contract as it ships.

Every assertion reads a real render (`synthesize` + `render`, the path a consumer project gets),
never a template. The required tokens and caps were fixed in the SPEC before any template text
existed, so the templates are written to satisfy them — not the other way round.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest
import yaml

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

SKILL = ".claude/skills/project-knowledge/SKILL.md"
CODEX_SKILL = ".agents/skills/project-knowledge/SKILL.md"
REQUIRED_TOKENS = (
    "upsert-wiki",
    "--category fact",
    "memory_retrieve",
    "Supersedes:",
    "auto-memory",
    "never record an inferred fact",
    "surface the stderr",
    "reuse only a [wiki:fact] slug",
)
TARGET_SETS = {
    "claude": [Target.CLAUDE_CODE],
    "cursor": [Target.CURSOR],
    "codex": [Target.CODEX],
    "all": [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX],
}
_FRONTMATTER_BLOCK = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL | re.MULTILINE)


def _render(preset: Preset, targets: list[Target], locale: str = "en") -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(), InterviewAnswers(preset=preset, targets=targets, locale=locale)
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        return {
            str(p.relative_to(root)): p.read_text(encoding="utf-8")
            for p in root.rglob("*")
            if p.is_file()
        }


# ── AC-004 ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE], ids=["production", "side"])
@pytest.mark.parametrize("target_set", sorted(TARGET_SETS))
def test_ac_004_skill_carries_capture_contract(preset: Preset, target_set: str) -> None:
    targets = TARGET_SETS[target_set]
    files = _render(preset, targets)
    expected_copies = [SKILL] + ([CODEX_SKILL] if Target.CODEX in targets else [])
    rendered_copies = [p for p in (SKILL, CODEX_SKILL) if p in files]
    assert rendered_copies == expected_copies
    for path in rendered_copies:
        skill_text = files[path]
        missing = [tok for tok in REQUIRED_TOKENS if tok not in skill_text]
        assert not missing, f"{path} lacks {missing}"


@pytest.mark.parametrize("target_set", ["claude", "codex"])
def test_skill_search_step_keeps_dri_text_out_of_the_shell(target_set: str) -> None:
    """Pins /hm:review round 2's fix (finding 3b1eeac67cfed281) so reverting it goes RED.

    The search words and the slug are the only agent-composed values that reach a shell
    command; the body goes through a Write-tool temp file. What keeps them inert is the
    restricted alphabet and the single quotes, so both are asserted on every rendered copy, and
    the pre-fix double-quoted `<subject>` interpolation must be gone.
    """
    targets = TARGET_SETS[target_set]
    files = _render(Preset.PRODUCTION, targets)
    for path in [SKILL] + ([CODEX_SKILL] if Target.CODEX in targets else []):
        skill = files[path]
        search = skill[skill.index("**Search first**") : skill.index("**Pick the slug")]
        assert "Never paste the DRI's wording into a command" in search
        assert "only letters," in search
        assert "digits, spaces and hyphens" in search
        assert "--topic '<search words>'" in search
        assert "<subject>" not in skill, "DRI-derived <subject> still reaches a command"
        assert "--slug '<slug>'" in skill
        assert "`[a-z0-9-]`" in skill


def test_skill_description_names_the_triggers() -> None:
    skill = _render(Preset.PRODUCTION, [Target.CLAUDE_CODE])[SKILL]
    descriptions = [
        meta["description"]
        for block in _FRONTMATTER_BLOCK.findall(skill)
        if isinstance(meta := yaml.safe_load(block), dict) and "description" in meta
    ]
    assert descriptions, "no description in any frontmatter block"
    description = str(descriptions[0])
    assert len(description) <= 250, len(description)
    for phrase in ("remember", "correct"):
        assert phrase in description.lower(), phrase


# ── AC-005 ───────────────────────────────────────────────────────────────────

from harness_maker.spec_machine import GoldenRow, load_golden_table  # noqa: E402

_SPEC_YAML = Path(__file__).parents[2] / "specs" / "SPEC-mission-context-loop.machine.yaml"
_AC005_ROWS = load_golden_table(_SPEC_YAML, "AC-005")
_POINTER_HEADING = "## Project knowledge"
_PRESETS = {"Production": Preset.PRODUCTION, "Side": Preset.SIDE}


def _pointer_section(text: str) -> str:
    start = text.index(_POINTER_HEADING)
    ends = [i for i in (text.find("\n## ", start + 1), text.find("\n<!--", start + 1)) if i != -1]
    return text[start : min(ends)] if ends else text[start:]


@pytest.mark.parametrize(
    "row",
    _AC005_ROWS,
    ids=[f"{r.input['file']}-{r.input['preset']}-{r.input['locale']}" for r in _AC005_ROWS],
)
def test_ac_005_pointer_present_and_bounded(row: GoldenRow) -> None:
    given, expected = row.input, row.expected
    files = _render(
        _PRESETS[str(given["preset"])],
        TARGET_SETS["all"],
        locale=str(given["locale"]),
    )
    rendered = files[str(given["file"])]
    assert rendered.count(_POINTER_HEADING) == 1, "pointer section missing or duplicated"
    section = _pointer_section(rendered).rstrip()
    assert len(section) <= int(str(expected["max_chars"])), (len(section), section)
    names = expected["names"]
    assert isinstance(names, list)
    missing = [n for n in names if str(n) not in section]
    assert not missing, f"{given['file']} pointer lacks {missing}: {section!r}"


# ── AC-006 ───────────────────────────────────────────────────────────────────

from harness_maker.models import DevMode  # noqa: E402

_WRAPUP_PATHS = {
    "claude": ".claude/commands/hm/wrapup.md",
    "codex": ".agents/skills/hm-wrapup/SKILL.md",
}


def _section_51(wrapup: str) -> str:
    start = wrapup.index("#### 5.1 ")
    return wrapup[start : wrapup.index("#### 5.2 ", start)]


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE], ids=["production", "side"])
@pytest.mark.parametrize("dev_mode", list(DevMode), ids=lambda d: d.value)
@pytest.mark.parametrize("variant", sorted(_WRAPUP_PATHS))
def test_ac_006_wrapup_51_searches_before_write(
    preset: Preset, dev_mode: DevMode, variant: str
) -> None:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=preset, targets=TARGET_SETS["all"], dev_mode=dev_mode),
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        wrapup = (root / _WRAPUP_PATHS[variant]).read_text(encoding="utf-8")
    section_51 = _section_51(wrapup)
    assert "memory_retrieve" in section_51, "5.1 has no search step"
    assert section_51.index("memory_retrieve") < section_51.index("upsert-wiki")
    assert "reuse" in section_51
    assert "never reuse a [wiki:fact] slug" in section_51


# ── AC-007 ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("locale", ["en", "ko"])
def test_ac_007_wiki_template_documents_fact_and_supersedes(locale: str) -> None:
    wiki = _render(Preset.PRODUCTION, TARGET_SETS["claude"], locale=locale)[
        ".claude/memory/wiki.md"
    ]
    category_lines = [ln for ln in wiki.splitlines() if "`category`:" in ln]
    assert category_lines, "no category line in the wiki template"
    for line in category_lines:
        # `> - `category`: pattern / convention / …` — the list after the colon, one token each.
        tokens = [t.strip().strip("`") for t in line.split("`category`:", 1)[1].split("/")]
        assert "fact" in tokens, tokens
    assert "Supersedes:" in wiki


# ── /hm:help row (ADR-006, validator C11) ────────────────────────────────────


@pytest.mark.parametrize("locale", ["en", "ko"])
def test_help_lists_project_knowledge(locale: str) -> None:
    files = _render(Preset.PRODUCTION, TARGET_SETS["all"], locale=locale)
    claude_help = files[".claude/commands/hm/help.md"]
    codex_help = files[".agents/skills/hm-help/SKILL.md"]
    assert "| project-knowledge |" in claude_help
    assert "@project-knowledge" not in claude_help
    assert "| project-knowledge |" in codex_help
    assert "@project-knowledge" in codex_help


# ── Codex P1 19b3f7f1f0100b4f (REVIEW 2026-09-19): exact-slug check before a new slug ──


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE], ids=["production", "side"])
@pytest.mark.parametrize("variant", sorted(_WRAPUP_PATHS))
def test_new_slug_is_checked_for_an_existing_heading(preset: Preset, variant: str) -> None:
    """A search is top-k, so a fact it does not surface can still own the slug you pick.

    The write replaces whatever entry holds the slug, category included, so both writers must
    check the EXACT slug against the base wiki's headings before using it as new — with the
    Grep tool, never a shell line, so the slug is not interpreted.
    """
    files = _render(preset, TARGET_SETS["all"])
    wrapup = files[_WRAPUP_PATHS[variant]]
    skill_paths = [SKILL] + ([CODEX_SKILL] if variant == "codex" else [])
    for text in [_section_51(wrapup)] + [files[p] for p in skill_paths]:
        assert "check the exact slug" in text
        assert "Grep tool" in text
        assert "## [wiki:" in text
        # /hm:review re-review P1 92cde7ba0790a79f / df86b130c1c70c27: naming "the base" is not
        # enough — from a task worktree the cwd copy is stale, so the rule to reach it is pinned.
        assert "two levels above" in text
        assert "stale" in text


# ── Codex P1 4444994ec2c7ab6f: a correction carries the first-recorded date forward ──


@pytest.mark.parametrize("locale", ["en", "ko"])
def test_correction_carries_the_first_recorded_date(locale: str) -> None:
    files = _render(Preset.PRODUCTION, TARGET_SETS["all"], locale=locale)
    for path in (SKILL, CODEX_SKILL, ".claude/memory/wiki.md"):
        assert "first recorded <YYYY-MM-DD>" in files[path], path
