"""Phase 1 — preset default maps + 3-tier resolve_agent_spec.

ADR-005: 3-tier resolution chain (explicit override → preset map → default_model fallback).
"""

from pathlib import Path

from harness_maker.models import AgentModelSpec, CodexAgentSpec, HarnessConfig, Preset
from harness_maker.presets import (
    PRESET_AGENT_MODELS,
    _spec_from_default_model,
    resolve_agent_spec,
)


def test_preset_agent_models_has_both_presets() -> None:
    assert Preset.PRODUCTION in PRESET_AGENT_MODELS
    assert Preset.SIDE in PRESET_AGENT_MODELS


def test_preset_agent_models_completeness_vs_shipped_templates() -> None:
    """Every agent in ``_ALL_AGENTS`` has both a template AND Production / Side
    preset entries.

    REVIEW Phase 5 CP-1 fix (was Phase 2 R-2): authority shifted from
    ``templates/agents/*.md.j2`` set to ``synthesize._ALL_AGENTS``. Dormant
    templates (file exists but agent not in any iteration list) are tolerated
    — they neither require a preset entry nor render to disk. This tightens
    the symmetry rule to the triangle (template ↔ _ALL_AGENTS ↔ preset map)
    instead of the previous 2-leg shape that allowed trajectory-monitor to
    drift.
    """
    from harness_maker.synthesize import _ALL_AGENTS

    agents_dir = (
        Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates" / "agents"
    )
    template_names: set[str] = set()
    for path in agents_dir.glob("*.md.j2"):
        # path.stem for "foo.md.j2" is "foo.md"; strip the .md too.
        name = path.stem
        if name.endswith(".md"):
            name = name[:-3]
        # Skip _body fragments (included by main agent file, not standalone).
        if name.endswith("_body"):
            continue
        template_names.add(name)

    all_agents = set(_ALL_AGENTS)
    prod = set(PRESET_AGENT_MODELS[Preset.PRODUCTION].keys())
    side = set(PRESET_AGENT_MODELS[Preset.SIDE].keys())

    # Every active agent must have a template.
    assert all_agents <= template_names, (
        f"_ALL_AGENTS members missing a template: {sorted(all_agents - template_names)}"
    )
    # Every active agent must have BOTH preset entries.
    missing_prod = all_agents - prod
    missing_side = all_agents - side
    assert not missing_prod, f"Production preset missing for _ALL_AGENTS: {sorted(missing_prod)}"
    assert not missing_side, f"Side preset missing for _ALL_AGENTS: {sorted(missing_side)}"
    # Preset maps must NOT carry entries that aren't active (dead data).
    extra_prod = prod - all_agents
    extra_side = side - all_agents
    assert not extra_prod, (
        f"Production preset extras (not in _ALL_AGENTS): {sorted(extra_prod)} "
        "— if these are intentional dormant placeholders, remove the preset "
        "entry (templates may stay)."
    )
    assert not extra_side, (
        f"Side preset extras (not in _ALL_AGENTS): {sorted(extra_side)} "
        "— if these are intentional dormant placeholders, remove the preset "
        "entry (templates may stay)."
    )
    # Dormant templates (template exists but agent absent from _ALL_AGENTS)
    # are allowed — log them for visibility but do not fail the test.
    dormant = template_names - all_agents
    # No assertion on `dormant` — informational only.
    _ = dormant


def test_resolve_agent_spec_tier1_explicit_override_beats_preset() -> None:
    """ADR-005 Tier 1: agent_models override wins over preset map."""
    custom = AgentModelSpec(
        claude="haiku",
        codex=CodexAgentSpec(reasoning_effort="minimal"),
    )
    config = HarnessConfig(preset=Preset.PRODUCTION, agent_models={"autoloop-coder": custom})
    spec = resolve_agent_spec("autoloop-coder", config)
    assert spec.claude == "haiku"
    assert spec.codex is not None
    assert spec.codex.reasoning_effort == "minimal"


def test_resolve_agent_spec_tier2_preset_production_reasoning_agent() -> None:
    """Tier 2: Production preset → autoloop-coder gets opus."""
    config = HarnessConfig(preset=Preset.PRODUCTION)
    spec = resolve_agent_spec("autoloop-coder", config)
    assert spec.claude == "opus"
    assert spec.cursor is None, "the removed Cursor target leaves no preset cursor model"


def test_resolve_agent_spec_tier2_preset_side_downshifts() -> None:
    """Tier 2: Side preset → autoloop-coder gets sonnet (downshifted from opus)."""
    config = HarnessConfig(preset=Preset.SIDE)
    spec = resolve_agent_spec("autoloop-coder", config)
    assert spec.claude == "sonnet"


def test_resolve_agent_spec_tier3_user_authored_agent_no_keyerror() -> None:
    """ADR-005 Tier 3 (validator C-2 fix): user-authored agent absent from preset
    map falls through to default_model-derived spec — never KeyErrors."""
    config = HarnessConfig(preset=Preset.PRODUCTION, default_model="claude-opus-4-7")
    spec = resolve_agent_spec("my-custom-domain-agent", config)
    assert spec.claude == "opus"
    assert spec.codex is not None
    assert spec.codex.reasoning_effort == "medium"


def test_spec_from_default_model_handles_known_families() -> None:
    """Tier 3 helper derives alias from default_model family."""
    cases = [
        ("claude-opus-4-7", "opus"),
        ("claude-sonnet-4-6", "sonnet"),
        ("claude-haiku-4-5", "haiku"),
    ]
    for model_id, expected_alias in cases:
        spec = _spec_from_default_model(model_id)
        assert spec.claude == expected_alias, (
            f"{model_id!r} → claude={spec.claude!r}, expected {expected_alias!r}"
        )
        assert spec.codex is not None
        assert spec.codex.reasoning_effort == "medium"


def test_spec_from_default_model_safe_fallback_for_unknown() -> None:
    """Unknown model id → safe sonnet fallback (never crashes)."""
    spec = _spec_from_default_model("some-future-model")
    assert spec.claude == "sonnet"
    assert spec.codex is not None
    assert spec.codex.reasoning_effort == "medium"
