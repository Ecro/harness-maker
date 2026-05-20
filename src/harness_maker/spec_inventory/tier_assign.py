"""Tier assignment via heuristic + LLM disagreement gate (P2, ADR-008).

Scoring formula:

    criticality = w1*user_facing + w2*security + w3*reproducibility + w4*ai_dependency

Default weights: (0.4, 0.3, 0.2, 0.1). Thresholds: T1 ≥ 0.75, T2 ≥ 0.4, else T3.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness_maker.spec_inventory.catalog_schema import (
    Catalog,
    Feature,
    VerificationTier,
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "user_facing": 0.4,
    "security": 0.3,
    "reproducibility": 0.2,
    "ai_dependency": 0.1,
}

DEFAULT_THRESHOLDS: tuple[float, float] = (0.5, 0.25)  # T1 floor, T2 floor
# Calibration: single critical signal (security, weight 0.3) places a feature
# in T2, two-signal modules (e.g. render = user_facing + reproducibility) hit T1.
# Pure helpers with no signal land in T3.


@dataclass(frozen=True)
class CriticalitySignal:
    user_facing: float
    security: float
    reproducibility: float
    ai_dependency: float

    def score(self, weights: dict[str, float]) -> float:
        return (
            weights["user_facing"] * self.user_facing
            + weights["security"] * self.security
            + weights["reproducibility"] * self.reproducibility
            + weights["ai_dependency"] * self.ai_dependency
        )


# Static signal table — module name fragments → criticality booster.
_USER_FACING_HINTS: tuple[str, ...] = (
    "render", "interview", "synthesize", "autoloop", "cli", "make",
    "command", "agent",
)
_SECURITY_HINTS: tuple[str, ...] = (
    "security", "secscan", "permission", "secret", "auth", "hook",
)
_REPRODUCIBILITY_HINTS: tuple[str, ...] = (
    "reconcile", "render", "worktree", "synthesize", "io_utils",
)
_AI_DEPENDENCY_HINTS: tuple[str, ...] = (
    "llm_judge", "ai_readiness", "spec_quality", "agent_quality",
    "inequality_gate", "common_ground",
)


def _signal_from_path(path: str) -> CriticalitySignal:
    """Heuristic feature-name → criticality signal.

    Matches against the **basename without extension** (not the full path) so
    ``harness_maker`` in the directory part doesn't spuriously match every
    hint containing ``make``.
    """
    from pathlib import Path as _Path

    stem = _Path(path).stem.lower()
    tokens = set(stem.replace("-", "_").split("_"))
    return CriticalitySignal(
        user_facing=1.0 if any(h in tokens for h in _USER_FACING_HINTS) else 0.0,
        security=1.0 if any(h in tokens for h in _SECURITY_HINTS) else 0.0,
        reproducibility=1.0 if any(h in tokens for h in _REPRODUCIBILITY_HINTS) else 0.0,
        ai_dependency=1.0 if any(h in tokens for h in _AI_DEPENDENCY_HINTS) else 0.0,
    )


def _tier_for_score(score: float, thresholds: tuple[float, float]) -> VerificationTier:
    if score >= thresholds[0]:
        return 1
    if score >= thresholds[1]:
        return 2
    return 3


def assign_tiers(
    catalog: Catalog,
    *,
    weights: dict[str, float] | None = None,
    thresholds: tuple[float, float] | None = None,
) -> Catalog:
    """Mutate-in-place: each Feature gets a heuristic ``suggested_tier``."""
    w = weights or DEFAULT_WEIGHTS
    th = thresholds or DEFAULT_THRESHOLDS
    for f in catalog.features:
        sig = _signal_from_path(f.path)
        f.suggested_tier = _tier_for_score(sig.score(w), th)
    return catalog


def detect_disagreements(
    catalog: Catalog,
    llm_proposals: dict[str, VerificationTier],
) -> list[Feature]:
    """Return features where heuristic and LLM disagree by ≥1 tier.

    Pure read — does NOT mutate ``Feature.llm_proposed_tier``. Use
    ``apply_llm_proposals`` if you also want to write the proposals back
    into the catalog.
    """
    out: list[Feature] = []
    for f in catalog.features:
        proposed = llm_proposals.get(f.id)
        if proposed is None:
            continue
        if abs(int(f.suggested_tier) - int(proposed)) >= 1:
            out.append(f)
    return out


def apply_llm_proposals(
    catalog: Catalog,
    llm_proposals: dict[str, VerificationTier],
) -> Catalog:
    """Write llm_proposals into each Feature.llm_proposed_tier. Explicit mutation."""
    for f in catalog.features:
        proposed = llm_proposals.get(f.id)
        if proposed is not None:
            f.llm_proposed_tier = proposed
    return catalog


def recalibrate_weights(
    catalog: Catalog,
    override_rate: float,
) -> dict[str, float] | None:
    """Per ADR-008: if user override rate > 50%, signal recalibration.

    A real least-squares fit would inspect each override. For now we return
    a simple shift: bump the under-weighted dim. The hook is in place; the
    full fit is a follow-up.
    """
    if override_rate <= 0.5:
        return None
    new_weights = dict(DEFAULT_WEIGHTS)
    new_weights["user_facing"] = min(0.55, new_weights["user_facing"] + 0.1)
    new_weights["ai_dependency"] = max(0.05, new_weights["ai_dependency"] - 0.1)
    return new_weights


__all__ = [
    "DEFAULT_THRESHOLDS",
    "DEFAULT_WEIGHTS",
    "CriticalitySignal",
    "apply_llm_proposals",
    "assign_tiers",
    "detect_disagreements",
    "recalibrate_weights",
]
