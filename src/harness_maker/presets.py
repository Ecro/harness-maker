"""Preset-aware per-agent model defaults + 3-tier render resolution.

ADR-005 (PLAN-model-routing-multi-ide):
    Tier 1 — config.agent_models[name] (explicit user override)
    Tier 2 — PRESET_AGENT_MODELS[preset][name] (preset default for shipped agents)
    Tier 3 — _spec_from_default_model(config.default_model) (catch-all for
              user-authored agents; never KeyErrors — validator C-2 fix).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from harness_maker.models import AgentModelSpec, CodexAgentSpec, Preset

if TYPE_CHECKING:
    from harness_maker.models import HarnessConfig


# ──────────────────────────────────────────────────────────────────────────────
# Preset default maps (ADR-005)
# ──────────────────────────────────────────────────────────────────────────────


_Effort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]


def _spec(claude_alias: str, effort: _Effort) -> AgentModelSpec:
    """Convenience: build a spec from a Claude alias and a Codex reasoning effort.

    Typed `effort: _Effort` (not str) so mypy catches a typo in any of the 28
    preset entries — without this, only the runtime Pydantic validator would
    catch them (review code-reviewer P2).
    """
    return AgentModelSpec(
        claude=claude_alias,
        codex=CodexAgentSpec(reasoning_effort=effort),
    )


# Production. **The axis is CALL VOLUME, not "reasoning vs structured"** — that older
# description did not survive reading the map beside it. `spec-validator` (opus) and
# `code-reviewer` (sonnet) both critique a draft; only the name differs. What actually predicts
# a row is how often the agent runs: the eleven reviewers fire 7-at-a-time, twice per review
# round, several rounds per task, so they dominate spend and sit on sonnet; the rest run once
# per stage or less and can afford opus.
#
# Two rows are deliberate exceptions to the volume rule, each for a stated reason:
#   * `stage-delegate` — the most PROCEDURAL agent here (frontmatter edit, checkbox
#     substitution, a handful of CLI calls, return a receipt). Volume is low, but a checklist
#     does not need opus, and the receipt is reconciled against disk before anything commits.
#   * `code-verifier` — low volume, but its mode-B disposition decides whether a cross-model
#     finding gets a VOTE. A wrong call there deletes a finding silently, and nothing
#     downstream can tell. It is the one place a cheap judgment is unrecoverable.
#
# (0.64.0: `stuck`, `executor`, `security-auditor` and `autoloop-coder` retired with their stages;
# their entries went with them, and an `agent_models` override naming one is an inert-key warning.)
#
# (REVIEW Phase 5 CP-1: trajectory-monitor removed — agent is dormant, not in
# `synthesize._ALL_AGENTS` / `_ALL_SKILLS` / `_COMMUNICATION_VARIANT`. Reactivate by adding to
# those tables AND restoring the entry here.)
_PRODUCTION_MAP: dict[str, AgentModelSpec] = {
    # Low volume — opus is affordable here
    "spec-validator": _spec("opus", "high"),
    # Low volume, but PROCEDURAL — see the exception note above
    "stage-delegate": _spec("sonnet", "medium"),
    # Low volume, and the one cheap judgment that is unrecoverable — see the note above
    "code-verifier": _spec("opus", "high"),
    # High volume — 7 lenses x 2 passes x N rounds
    "code-reviewer": _spec("sonnet", "medium"),
    "concurrency-reviewer": _spec("sonnet", "medium"),
    "consensus-arbiter": _spec("sonnet", "medium"),
    "judgment-reviewer": _spec("sonnet", "medium"),
    "performance-reviewer": _spec("sonnet", "medium"),
    "security-reviewer": _spec("sonnet", "medium"),
    "test-reviewer": _spec("sonnet", "medium"),
    "ux-reviewer": _spec("sonnet", "medium"),
}


# Side: everything downshifted to sonnet; reasoning agents stay at medium effort,
# reviewers drop to low. (CP-1: trajectory-monitor removed — see _PRODUCTION_MAP comment.)
_SIDE_MAP: dict[str, AgentModelSpec] = {
    # Reasoning agents (still need decent quality even in Side)
    "spec-validator": _spec("sonnet", "medium"),
    "stage-delegate": _spec("sonnet", "medium"),
    # Reviewers downshift
    "code-reviewer": _spec("sonnet", "low"),
    "code-verifier": _spec("sonnet", "low"),
    "concurrency-reviewer": _spec("sonnet", "low"),
    "consensus-arbiter": _spec("sonnet", "low"),
    "judgment-reviewer": _spec("sonnet", "low"),
    "performance-reviewer": _spec("sonnet", "low"),
    "security-reviewer": _spec("sonnet", "low"),
    "test-reviewer": _spec("sonnet", "low"),
    "ux-reviewer": _spec("sonnet", "low"),
}


PRESET_AGENT_MODELS: dict[Preset, dict[str, AgentModelSpec]] = {
    Preset.PRODUCTION: _PRODUCTION_MAP,
    Preset.SIDE: _SIDE_MAP,
}


# ──────────────────────────────────────────────────────────────────────────────
# 3-tier resolution (ADR-005)
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
        codex=CodexAgentSpec(reasoning_effort="medium"),
    )


def resolve_agent_spec(name: str, config: HarnessConfig) -> AgentModelSpec:
    """3-tier resolution for a given agent name.

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
    return spec
