"""Aggregate failures from all 3 layers into a ranked improvement plan.

Layer 1 (readiness.compute_readiness) produces deterministic dimension signals.
Layer 2 (llm_judge.judge_target) produces LLM-judged content verdicts.
Layer 3 (cache_diagnostics.diagnose_cache) produces a cache failure mode.

This module blends them into a single composite score and a flat list of
actionable items sorted by priority. The /hm:ai-readiness command renders
this plan to the user; the `improve` subcommand walks each item with
AskUserQuestion (accept / reject / defer).
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from harness_maker.cache_diagnostics import CacheDiagnosis
from harness_maker.llm_judge import JudgeResult
from harness_maker.readiness import ReadinessResult

# Layer weighting toward the final composite.
_LAYER_WEIGHTS: dict[str, float] = {
    "readiness": 0.70,
    "llm_judge": 0.25,
    "cache": 0.05,
}

# Priority ordering (lower = higher urgency).
_PRIORITY_RANK: dict[str, int] = {"P0": 0, "P1": 1, "P2": 2}


class ActionItem(BaseModel):
    """One concrete improvement to surface to the user."""

    model_config = ConfigDict(strict=True, extra="forbid")

    priority: str  # P0 | P1 | P2
    dimension: str
    target: str  # file path or logical area
    summary: str  # one-line description of the gap
    detail: str  # evidence (why it failed)
    suggestion: str  # how to fix
    source: str  # "layer1:signal_id" | "layer2:rubric_id@file" | "layer3:cache"


class ImprovementPlan(BaseModel):
    """Composite ai-readiness score + ranked list of improvement actions."""

    model_config = ConfigDict(strict=True, extra="forbid")

    composite_score: int  # 0-100
    layer_scores: dict[str, int]
    actions: list[ActionItem]


# ── priority assignment ────────────────────────────────────────────────────


def _layer1_priority(signal_weight: int) -> str:
    if signal_weight >= 25:
        return "P0"
    if signal_weight >= 15:
        return "P1"
    return "P2"


# ── action extractors ──────────────────────────────────────────────────────


def _extract_layer1_actions(readiness: ReadinessResult) -> list[ActionItem]:
    out: list[ActionItem] = []
    for dim_name, dim in readiness.dimensions.items():
        # governance on Side preset is intentionally skipped (weight 0).
        if dim_name == "governance" and readiness.weights.get("governance", 0) == 0:
            continue
        for sig in dim.signals:
            if sig.passed or sig.action is None:
                continue
            out.append(
                ActionItem(
                    priority=_layer1_priority(sig.weight),
                    dimension=dim_name,
                    target=dim_name,
                    summary=sig.evidence,
                    detail=f"Signal '{sig.id}' failed (weight {sig.weight} of dim 100)",
                    suggestion=sig.action,
                    source=f"layer1:{sig.id}",
                )
            )
    return out


def _extract_layer2_actions(judge_results: Iterable[JudgeResult]) -> list[ActionItem]:
    out: list[ActionItem] = []
    for jr in judge_results:
        if jr.error and not jr.verdicts:
            # Judge couldn't evaluate this file; surface as a soft warning.
            out.append(
                ActionItem(
                    priority="P2",
                    dimension=jr.dimension,
                    target=jr.file,
                    summary=f"LLM judge could not evaluate {jr.file}",
                    detail=jr.error,
                    suggestion="Re-run /hm:ai-readiness, or check Anthropic API access.",
                    source=f"layer2:error@{jr.file}",
                )
            )
            continue
        for v in jr.verdicts:
            if v.passed:
                continue
            priority = v.severity if v.severity in _PRIORITY_RANK else "P2"
            out.append(
                ActionItem(
                    priority=priority,
                    dimension=jr.dimension,
                    target=jr.file,
                    summary=f"{v.rubric_id}: failed",
                    detail=v.evidence,
                    suggestion=v.suggestion or "(no suggestion provided)",
                    source=f"layer2:{v.rubric_id}@{jr.file}",
                )
            )
    return out


def _extract_layer3_actions(cache: CacheDiagnosis) -> list[ActionItem]:
    if cache.primary_failure is None or cache.primary_failure == "no_data":
        return []
    return [
        ActionItem(
            priority="P1",
            dimension="cache_efficiency",
            target=".claude/observability/metrics.jsonl",
            summary=f"Cache hit rate {cache.hit_rate}% — primary cause: {cache.primary_failure}",
            detail=cache.evidence,
            suggestion=cache.remediation,
            source="layer3:cache",
        )
    ]


# ── composite ─────────────────────────────────────────────────────────────


def _layer2_score(judge_results: list[JudgeResult]) -> int:
    if not judge_results:
        return 50  # neutral when L2 didn't run
    return round(sum(r.score for r in judge_results) / len(judge_results))


def _composite(layer_scores: dict[str, int]) -> int:
    weighted = sum(layer_scores.get(k, 50) * w for k, w in _LAYER_WEIGHTS.items())
    return max(0, min(100, round(weighted)))


# ── action sorting ─────────────────────────────────────────────────────────


def _sort_actions(actions: list[ActionItem]) -> list[ActionItem]:
    return sorted(
        actions,
        key=lambda a: (_PRIORITY_RANK.get(a.priority, 99), a.dimension, a.source),
    )


# ── public API ────────────────────────────────────────────────────────────


def build_improvement_plan(
    readiness: ReadinessResult,
    judge_results: list[JudgeResult],
    cache_diagnosis: CacheDiagnosis,
) -> ImprovementPlan:
    """Combine all 3 layers into a composite score + ranked action list."""
    layer_scores: dict[str, int] = {
        "readiness": readiness.composite,
        "llm_judge": _layer2_score(judge_results),
        "cache": cache_diagnosis.score,
    }
    composite = _composite(layer_scores)

    actions: list[ActionItem] = []
    actions.extend(_extract_layer1_actions(readiness))
    actions.extend(_extract_layer2_actions(judge_results))
    actions.extend(_extract_layer3_actions(cache_diagnosis))

    return ImprovementPlan(
        composite_score=composite,
        layer_scores=layer_scores,
        actions=_sort_actions(actions),
    )
