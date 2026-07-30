"""Phase 7 tests: Codex skills dual-render + 7 stage skills.

RED before Phase 7:
- templates/codex/stage_skill.md.j2 does not exist
- _codex_stage_skills() returns [] (stub)
- _codex_target_files() lacks .agents/skills/ paths

GREEN after Phase 7:
- stage_skill.md.j2 renders valid SKILL.md frontmatter
- hm-research skill description mentions "harness-maker research stage"
- _codex_target_files() includes 9 existing + 7 stage + 1 loop = 19 skill paths

ADR-001 overrides ADR-008: stage skills now embed procedure bodies directly,
not via AGENTS.md reference. The AGENTS.md assertion has been removed.
"""

from __future__ import annotations

import pytest

from harness_maker.render import _make_env
from harness_maker.synthesize import (
    _ALL_SKILLS,
    _ATOMIC_STAGES,
    _codex_stage_skills,
    _codex_target_files,
)

_STAGES = _ATOMIC_STAGES  # ["research", "spec", "plan", "execute", "review", "wrapup", "verify"]


def _render_stage_skill(stage: str) -> str:
    env = _make_env()
    tpl = env.get_template("codex/stage_skill.md.j2")
    return tpl.render(stage=stage)


# ── stage_skill.md.j2 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("stage", _STAGES)
def test_stage_skill_renders_non_empty(stage: str) -> None:
    """codex/stage_skill.md.j2 must render non-empty content for each stage."""
    rendered = _render_stage_skill(stage)
    assert rendered.strip(), f"Stage skill for {stage!r} rendered empty"


@pytest.mark.parametrize("stage", _STAGES)
def test_stage_skill_has_yaml_frontmatter(stage: str) -> None:
    """Stage skill SKILL.md must start with YAML frontmatter (---\\n)."""
    rendered = _render_stage_skill(stage)
    assert rendered.startswith("---\n"), f"Stage skill {stage!r} missing YAML frontmatter"


@pytest.mark.parametrize("stage", _STAGES)
def test_stage_skill_has_name_field(stage: str) -> None:
    """Stage skill frontmatter must contain name: hm-<stage>."""
    rendered = _render_stage_skill(stage)
    assert f"name: hm-{stage}" in rendered, (
        f"Stage skill {stage!r} missing 'name: hm-{stage}' in frontmatter"
    )


@pytest.mark.parametrize("stage", _STAGES)
def test_stage_skill_has_description_field(stage: str) -> None:
    """Stage skill frontmatter must contain a non-empty description."""
    rendered = _render_stage_skill(stage)
    assert "description:" in rendered, (
        f"Stage skill {stage!r} missing 'description:' in frontmatter"
    )


def test_stage_skill_research_mentions_harness_maker() -> None:
    """hm-research SKILL.md must mention 'harness-maker' in description.

    ADR-001 overrides ADR-008: procedures are embedded in the skill body, not
    delegated via AGENTS.md. The AGENTS.md assertion is intentionally removed.
    """
    rendered = _render_stage_skill("research")
    assert "harness-maker" in rendered.lower(), (
        "hm-research skill missing 'harness-maker' reference"
    )
    assert "research stage" in rendered.lower(), (
        "hm-research skill description must mention 'research stage'"
    )


# ── synthesize: _codex_stage_skills ───────────────────────────────────────────


def test_codex_stage_skills_returns_7_entries() -> None:
    """_codex_stage_skills() must return 7 entries (one per atomic stage)."""
    specs = _codex_stage_skills()
    assert len(specs) == 7, f"Expected 7 stage skill specs, got {len(specs)}"


def test_codex_stage_skills_output_paths() -> None:
    """Each stage skill must have output path .agents/skills/hm-<stage>/SKILL.md."""
    specs = _codex_stage_skills()
    out_paths = {out for _, out, _ in specs}
    for stage in _STAGES:
        assert f".agents/skills/hm-{stage}/SKILL.md" in out_paths, (
            f"Missing stage skill output path for stage {stage!r}"
        )


# ── synthesize: _codex_target_files includes 9 + 7 + 1 + 1 = 18 skill paths ──


def test_codex_target_files_includes_existing_skills() -> None:
    """_codex_target_files() must include all 9 existing skills at .agents/skills/."""
    out_paths = {out for _, out, _ in _codex_target_files({})}
    for skill in _ALL_SKILLS:
        assert f".agents/skills/{skill}/SKILL.md" in out_paths, (
            f"_codex_target_files missing existing skill {skill!r}"
        )


def test_codex_target_files_includes_stage_skills() -> None:
    """_codex_target_files() must include all 7 stage skills at .agents/skills/hm-<stage>/."""
    out_paths = {out for _, out, _ in _codex_target_files({})}
    for stage in _STAGES:
        assert f".agents/skills/hm-{stage}/SKILL.md" in out_paths, (
            f"_codex_target_files missing stage skill hm-{stage!r}"
        )


def test_codex_target_files_total_skill_count() -> None:
    """_codex_target_files({}) emits 9 base + 7 stage + 1 loop + 1 loop-p5-batch + 1 help = 19.

    ADR-0007 (0.22.3) removed 2 skills (research-crawler + relevance-filter)
    when scrapping the external_risks layer; base count dropped 11 → 9.
    loop-p5-batch skill added (PLAN-latency-worktree-step-preview ADR-006);
    count 18 → 19.
    """
    out_paths = [out for _, out, _ in _codex_target_files({}) if out.startswith(".agents/skills/")]
    # 19 → 20 (2026-07-30, PLAN-second-opinion-acceptance-gate ADR-011): the
    # `second-opinion-gate` skill. This is the second of two enumeration constants the new
    # skill moved — `[fail:test] enumeration-tests-not-updated-with-new-rendered-artifact`
    # is exactly this family, so if a third one surfaces later, look for a count these two
    # greps missed rather than assuming the render is wrong.
    assert len(out_paths) == 20, f"Expected 20 skill paths, got {len(out_paths)}"
