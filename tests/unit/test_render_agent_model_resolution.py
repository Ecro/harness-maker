"""Phase 3 — renderer wires resolve_agent_spec into agent .md.j2 contexts.

ADR-005 3-tier resolution applied at synthesize._agent_files; the agent
templates use `model: {{ claude_model }}` instead of hardcoded aliases.
Validator C-2 fix: Tier-3 user-authored agent must not KeyError.
"""

from __future__ import annotations

from typing import Any

from harness_maker.models import (
    AgentModelSpec,
    CodexAgentSpec,
    HarnessConfig,
    Preset,
)
from harness_maker.presets import CURSOR_MODEL_IDS, resolve_agent_spec
from harness_maker.synthesize import _agent_files


def _spec_for(name: str, file_specs: list[tuple[str, str, dict[str, Any]]]) -> dict[str, Any]:
    for _tmpl, dst, ctx in file_specs:
        if dst == f"agents/{name}.md":
            return ctx
    raise AssertionError(f"agent {name!r} not in file_specs")


def test_tier1_explicit_override_beats_preset() -> None:
    """Override in agent_models takes precedence over preset map."""
    custom = AgentModelSpec(
        claude="haiku",
        cursor="haiku",
        codex=CodexAgentSpec(reasoning_effort="minimal"),
    )
    specs = _agent_files(
        preset=Preset.PRODUCTION,
        agent_models={"autoloop-coder": custom},
    )
    ctx = _spec_for("autoloop-coder", specs)
    assert ctx["claude_model"] == "haiku"
    # Cursor field normalized to concrete ID via CURSOR_MODEL_IDS.
    assert ctx["cursor_model"] == CURSOR_MODEL_IDS["haiku"]
    assert ctx["codex_reasoning_effort"] == "minimal"


def test_tier2_preset_production_reasoning_agent() -> None:
    """Production preset → autoloop-coder context has claude=opus."""
    specs = _agent_files(preset=Preset.PRODUCTION)
    ctx = _spec_for("autoloop-coder", specs)
    assert ctx["claude_model"] == "opus"
    assert ctx["cursor_model"] == CURSOR_MODEL_IDS["opus"]
    assert ctx["codex_reasoning_effort"] == "high"


def test_tier2_preset_side_downshifts_reasoning_agent() -> None:
    """Side preset → autoloop-coder context has claude=sonnet (downshifted)."""
    specs = _agent_files(preset=Preset.SIDE)
    ctx = _spec_for("autoloop-coder", specs)
    assert ctx["claude_model"] == "sonnet"
    assert ctx["cursor_model"] == CURSOR_MODEL_IDS["sonnet"]
    assert ctx["codex_reasoning_effort"] == "medium"


def test_resolve_agent_spec_directly_for_user_authored_agent() -> None:
    """Validator C-2 fix: a user-authored agent absent from PRESET_AGENT_MODELS
    falls through Tier 3 to default_model-derived spec — never KeyErrors.

    (synthesize._agent_files only iterates shipped agents; Tier-3 protection
    is tested via the resolve_agent_spec call surface directly because that's
    what Phase 6 /hm:health and future user-added agent contexts will hit.)
    """
    config = HarnessConfig(
        preset=Preset.PRODUCTION,
        default_model="claude-opus-4-7",
    )
    spec = resolve_agent_spec("my-custom-domain-agent", config)
    assert spec.claude == "opus"
    assert spec.cursor == CURSOR_MODEL_IDS["opus"]
    assert spec.codex is not None
    assert spec.codex.reasoning_effort == "medium"
