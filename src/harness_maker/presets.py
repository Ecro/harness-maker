"""Preset-aware per-agent model defaults + 3-tier render resolution.

ADR-005 (PLAN-model-routing-multi-ide):
    Tier 1 — config.agent_models[name] (explicit user override)
    Tier 2 — PRESET_AGENT_MODELS[preset][name] (preset default for shipped agents)
    Tier 3 — _spec_from_default_model(config.default_model) (catch-all for
              user-authored agents; never KeyErrors — validator C-2 fix).

ADR-003 R5: cursor alias normalization happens here at the render boundary.
Users write aliases (``cursor: opus``) in harness.yaml; this module normalizes
to concrete IDs via CURSOR_MODEL_IDS. Concrete IDs hand-authored in harness.yaml
pass through unchanged. ADR-010 sub-check (b) inspects PRE-resolution values
directly from ``config.agent_models[name].cursor`` (not from
``resolve_agent_spec(...).cursor``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from harness_maker.models import AgentModelSpec, CodexAgentSpec, Preset

if TYPE_CHECKING:
    from harness_maker.models import HarnessConfig


# ──────────────────────────────────────────────────────────────────────────────
# Canonical alias → concrete-ID table (ADR-003 R5 + W-4)
# ──────────────────────────────────────────────────────────────────────────────
# Single source of truth for Cursor concrete IDs. Templates MUST NOT embed raw
# concrete IDs (enforced by tests/unit/test_no_raw_cursor_model_ids_in_templates.py).
# A future Claude release = update this dict in one place, re-render snapshots.
CURSOR_MODEL_IDS: dict[str, str] = {
    "opus": "claude-4-7-opus",
    "sonnet": "claude-4-6-sonnet",
    "haiku": "claude-4-5-haiku",
}


# ──────────────────────────────────────────────────────────────────────────────
# Preset default maps (ADR-005)
# ──────────────────────────────────────────────────────────────────────────────


_Effort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]


def _spec(claude_alias: str, effort: _Effort) -> AgentModelSpec:
    """Convenience: build a uniform spec where Claude alias === Cursor alias.

    Cursor alias gets normalized to concrete ID at the render boundary via
    `_normalize_cursor_alias`, so writing the alias here keeps the preset map
    portable across Claude releases (single update in CURSOR_MODEL_IDS).

    Typed `effort: _Effort` (not str) so mypy catches a typo in any of the 28
    preset entries — without this, only the runtime Pydantic validator would
    catch them (review code-reviewer P2).
    """
    return AgentModelSpec(
        claude=claude_alias,
        cursor=claude_alias,
        codex=CodexAgentSpec(reasoning_effort=effort),
    )


# Production: reasoning agents get opus + high effort; reviewers get sonnet +
# medium. (REVIEW Phase 5 CP-1: trajectory-monitor removed — agent is dormant,
# not in `synthesize._ALL_AGENTS` / `_ALL_SKILLS` / `_COMMUNICATION_VARIANT`.
# Reactivate by adding to those tables AND restoring the entry here.)
_PRODUCTION_MAP: dict[str, AgentModelSpec] = {
    # Reasoning-heavy
    "autoloop-coder": _spec("opus", "high"),
    "plan-validator": _spec("opus", "high"),
    "stage-delegate": _spec("opus", "high"),
    "stuck": _spec("opus", "high"),
    # Reviewer / structured agents
    "code-reviewer": _spec("sonnet", "medium"),
    "code-verifier": _spec("sonnet", "medium"),
    "concurrency-reviewer": _spec("sonnet", "medium"),
    "consensus-arbiter": _spec("sonnet", "medium"),
    "executor": _spec("sonnet", "medium"),
    "judgment-reviewer": _spec("sonnet", "medium"),
    "performance-reviewer": _spec("sonnet", "medium"),
    "security-auditor": _spec("sonnet", "medium"),
    "security-reviewer": _spec("sonnet", "medium"),
    "test-reviewer": _spec("sonnet", "medium"),
    "ux-reviewer": _spec("sonnet", "medium"),
}


# Side: everything downshifted to sonnet; reasoning agents stay at medium effort,
# reviewers drop to low. (CP-1: trajectory-monitor removed — see _PRODUCTION_MAP comment.)
_SIDE_MAP: dict[str, AgentModelSpec] = {
    # Reasoning agents (still need decent quality even in Side)
    "autoloop-coder": _spec("sonnet", "medium"),
    "plan-validator": _spec("sonnet", "medium"),
    "stage-delegate": _spec("sonnet", "medium"),
    "stuck": _spec("sonnet", "medium"),
    # Reviewers downshift
    "code-reviewer": _spec("sonnet", "low"),
    "code-verifier": _spec("sonnet", "low"),
    "concurrency-reviewer": _spec("sonnet", "low"),
    "consensus-arbiter": _spec("sonnet", "low"),
    "executor": _spec("sonnet", "low"),
    "judgment-reviewer": _spec("sonnet", "low"),
    "performance-reviewer": _spec("sonnet", "low"),
    "security-auditor": _spec("sonnet", "low"),
    "security-reviewer": _spec("sonnet", "low"),
    "test-reviewer": _spec("sonnet", "low"),
    "ux-reviewer": _spec("sonnet", "low"),
}


PRESET_AGENT_MODELS: dict[Preset, dict[str, AgentModelSpec]] = {
    Preset.PRODUCTION: _PRODUCTION_MAP,
    Preset.SIDE: _SIDE_MAP,
}


# ──────────────────────────────────────────────────────────────────────────────
# 3-tier resolution + cursor alias normalization (ADR-003 R5 + ADR-005)
# ──────────────────────────────────────────────────────────────────────────────


def _spec_from_default_model(default_model: str) -> AgentModelSpec:
    """Tier-3 fallback (validator C-2 fix): synthesize a spec from the
    floor ``default_model`` string. Catches user-authored agents that appear
    in neither ``config.agent_models`` nor ``PRESET_AGENT_MODELS[preset]``.

    Heuristic: derive the alias from the family substring (opus/sonnet/haiku).
    Unknown families fall back to ``sonnet`` (mid-tier safe default).

    Substring priority is intentionally ordered opus > sonnet > haiku — a
    hypothetical model name containing multiple family words (e.g. an
    ``opus-sonnet-blend`` test build) deterministically maps to ``opus``
    (the highest-capability family). Reorder only with paired test updates
    (see review consensus-passed P2 + security-reviewer P2).
    """
    if "opus" in default_model:
        alias = "opus"
    elif "sonnet" in default_model:
        alias = "sonnet"
    elif "haiku" in default_model:
        alias = "haiku"
    else:
        alias = "sonnet"
    return AgentModelSpec(
        claude=alias,
        cursor=alias,
        codex=CodexAgentSpec(reasoning_effort="medium"),
    )


def _normalize_cursor_alias(spec: AgentModelSpec) -> AgentModelSpec:
    """ADR-003 R5: alias-form cursor values are normalized to concrete IDs at
    render boundary. Concrete IDs (not in CURSOR_MODEL_IDS keys) pass through
    unchanged.
    """
    if spec.cursor and spec.cursor in CURSOR_MODEL_IDS:
        return spec.model_copy(update={"cursor": CURSOR_MODEL_IDS[spec.cursor]})
    return spec


def resolve_agent_spec(name: str, config: HarnessConfig) -> AgentModelSpec:
    """3-tier resolution + cursor alias normalization for a given agent name.

    Render-time entry point — every agent template renders via this function.
    """
    # Tier 1: explicit user override
    spec = config.agent_models.get(name)
    # Tier 2: preset default (only for shipped agents)
    if spec is None:
        spec = PRESET_AGENT_MODELS[config.preset].get(name)
    # Tier 3: default_model-derived (catches user-authored custom agents)
    if spec is None:
        spec = _spec_from_default_model(config.default_model)
    return _normalize_cursor_alias(spec)
