"""Phase 1 — preset default maps + 3-tier resolve_agent_spec + cursor alias normalization.

ADR-003 R5: CURSOR_MODEL_IDS canonical table; renderer normalizes alias at boundary.
ADR-005: 3-tier resolution chain (explicit override → preset map → default_model fallback).
"""

import re
from pathlib import Path

from harness_maker.models import AgentModelSpec, CodexAgentSpec, HarnessConfig, Preset
from harness_maker.presets import (
    CURSOR_MODEL_IDS,
    PRESET_AGENT_MODELS,
    _normalize_cursor_alias,
    _spec_from_default_model,
    resolve_agent_spec,
)


def test_preset_agent_models_has_both_presets() -> None:
    assert Preset.PRODUCTION in PRESET_AGENT_MODELS
    assert Preset.SIDE in PRESET_AGENT_MODELS


def test_preset_agent_models_completeness_vs_shipped_templates() -> None:
    """Every shipped agent in templates/agents/*.md.j2 has Production AND Side entries.

    This is the "adding a new agent forces a default map entry" contract from ADR-005.
    """
    agents_dir = (
        Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates" / "agents"
    )
    shipped_agents: set[str] = set()
    for path in agents_dir.glob("*.md.j2"):
        # path.stem for "foo.md.j2" is "foo.md"; strip the .md too.
        name = path.stem
        if name.endswith(".md"):
            name = name[:-3]
        # Skip _body fragments (included by main agent file, not standalone).
        if name.endswith("_body"):
            continue
        shipped_agents.add(name)

    prod = set(PRESET_AGENT_MODELS[Preset.PRODUCTION].keys())
    side = set(PRESET_AGENT_MODELS[Preset.SIDE].keys())

    missing_prod = shipped_agents - prod
    extra_prod = prod - shipped_agents
    missing_side = shipped_agents - side
    extra_side = side - shipped_agents
    assert not missing_prod, f"Production missing: {missing_prod}"
    assert not extra_prod, f"Production extras (no template): {extra_prod}"
    assert not missing_side, f"Side missing: {missing_side}"
    assert not extra_side, f"Side extras (no template): {extra_side}"


def test_cursor_model_ids_canonical_aliases_present() -> None:
    """ADR-003 R5: alias → concrete-ID mapping table covers the standard aliases."""
    assert "opus" in CURSOR_MODEL_IDS
    assert "sonnet" in CURSOR_MODEL_IDS
    assert "haiku" in CURSOR_MODEL_IDS


def test_cursor_model_ids_values_look_like_concrete_ids() -> None:
    """All concrete IDs match the claude-X-Y-{family} pattern."""
    for alias, concrete in CURSOR_MODEL_IDS.items():
        assert re.fullmatch(r"claude-\d+-\d+-\w+", concrete), (
            f"{alias!r} → {concrete!r} does not look like a concrete ID"
        )


def test_resolve_agent_spec_tier1_explicit_override_beats_preset() -> None:
    """ADR-005 Tier 1: agent_models override wins over preset map."""
    custom = AgentModelSpec(
        claude="haiku",
        cursor="haiku",
        codex=CodexAgentSpec(reasoning_effort="minimal"),
    )
    config = HarnessConfig(preset=Preset.PRODUCTION, agent_models={"autoloop-coder": custom})
    spec = resolve_agent_spec("autoloop-coder", config)
    assert spec.claude == "haiku"
    # Cursor field comes in as alias, gets normalized to concrete ID.
    assert spec.cursor == CURSOR_MODEL_IDS["haiku"]
    assert spec.codex is not None
    assert spec.codex.reasoning_effort == "minimal"


def test_resolve_agent_spec_tier2_preset_production_reasoning_agent() -> None:
    """Tier 2: Production preset → autoloop-coder gets opus."""
    config = HarnessConfig(preset=Preset.PRODUCTION)
    spec = resolve_agent_spec("autoloop-coder", config)
    assert spec.claude == "opus"
    assert spec.cursor == CURSOR_MODEL_IDS["opus"]


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
    assert spec.cursor == CURSOR_MODEL_IDS["opus"]
    assert spec.codex is not None
    assert spec.codex.reasoning_effort == "medium"


def test_resolve_agent_spec_normalizes_cursor_alias_in_user_override() -> None:
    """ADR-003 R5: user writes alias in cursor field → renderer normalizes."""
    custom = AgentModelSpec(cursor="opus")  # alias form
    config = HarnessConfig(preset=Preset.SIDE, agent_models={"foo": custom})
    spec = resolve_agent_spec("foo", config)
    assert spec.cursor == CURSOR_MODEL_IDS["opus"]


def test_resolve_agent_spec_preserves_concrete_cursor_id() -> None:
    """ADR-003 R5: user writes concrete ID → pass-through (no normalization)."""
    custom = AgentModelSpec(cursor="claude-4-6-sonnet")  # concrete ID
    config = HarnessConfig(preset=Preset.SIDE, agent_models={"foo": custom})
    spec = resolve_agent_spec("foo", config)
    assert spec.cursor == "claude-4-6-sonnet"


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


def test_normalize_cursor_alias_pass_through_when_none() -> None:
    """Spec with cursor=None passes through unchanged."""
    spec = AgentModelSpec(claude="opus", cursor=None)
    out = _normalize_cursor_alias(spec)
    assert out.cursor is None
    assert out.claude == "opus"


def test_normalize_cursor_alias_pass_through_when_concrete() -> None:
    """Spec with concrete-ID cursor passes through unchanged."""
    spec = AgentModelSpec(cursor="claude-4-6-sonnet")
    out = _normalize_cursor_alias(spec)
    assert out.cursor == "claude-4-6-sonnet"
