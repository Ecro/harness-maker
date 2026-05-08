"""Spec strength rubric — LLM-based spec quality evaluation (Phase 9, ADR-006).

Evaluates spec quality on 5 dimensions. In spec-driven mode, weak specs
are blocked; in task-driven mode, only warned.
"""

from __future__ import annotations

from typing import Any

from harness_maker.models import DevMode


class SpecQualityResult:
    """Result of spec quality evaluation."""

    def __init__(
        self,
        *,
        scores: dict[str, int],
        overall: int,
        weak_dimensions: list[str],
        blocked: bool,
        dev_mode: str,
    ) -> None:
        self.scores = scores
        self.overall = overall
        self.weak_dimensions = weak_dimensions
        self.blocked = blocked
        self.dev_mode = dev_mode

    @property
    def is_weak(self) -> bool:
        return self.overall < 60 or len(self.weak_dimensions) > 0


RUBRIC_DIMENSIONS: dict[str, str] = {
    "completeness": "All features, constraints, and edge cases specified",
    "testability": "Acceptance criteria are observable and verifiable",
    "unambiguity": "No vague qualifiers ('fast', 'good', 'important')",
    "consistency": "No internal contradictions between sections",
    "scope_boundary": "In-scope and out-of-scope clearly delineated",
}

_WEAK_THRESHOLD = 40


def evaluate_spec(
    spec_text: str,
    dev_mode: DevMode | str = DevMode.TASK_DRIVEN,
    *,
    judge: Any = None,
) -> SpecQualityResult:
    """Evaluate spec quality using rubric dimensions.

    When judge is None, uses heuristic scoring (keyword-based).
    When judge is provided, delegates to LLM for precise scoring.
    """
    if isinstance(dev_mode, str):
        try:
            dev_mode_enum = DevMode(dev_mode)
        except ValueError:
            dev_mode_enum = DevMode.TASK_DRIVEN
    else:
        dev_mode_enum = dev_mode

    scores = _judge_with_llm(spec_text, judge) if judge is not None else _heuristic_score(spec_text)

    weak_dims = [
        dim for dim, score in scores.items() if score < _WEAK_THRESHOLD
    ]
    overall = sum(scores.values()) // max(len(scores), 1)
    blocked = dev_mode_enum == DevMode.SPEC_DRIVEN and (
        overall < 60 or len(weak_dims) > 0
    )

    return SpecQualityResult(
        scores=scores,
        overall=overall,
        weak_dimensions=weak_dims,
        blocked=blocked,
        dev_mode=dev_mode_enum.value,
    )


def _heuristic_score(spec_text: str) -> dict[str, int]:
    """Keyword-based heuristic scoring (fallback when no LLM available)."""
    text_lower = spec_text.lower()
    scores: dict[str, int] = {}

    completeness_signals = ["scope", "feature", "constraint", "edge case", "requirement"]
    scores["completeness"] = min(
        100,
        sum(30 for s in completeness_signals if s in text_lower),
    )

    testability_signals = [
        "acceptance criteria", "then", "verify", "assert", "test",
        "observable", "measurable",
    ]
    scores["testability"] = min(
        100,
        sum(20 for s in testability_signals if s in text_lower),
    )

    vague_terms = ["fast", "good", "important", "better", "nice", "adequate", "proper"]
    vague_count = sum(1 for v in vague_terms if v in text_lower)
    scores["unambiguity"] = max(0, 100 - vague_count * 20)

    contradiction_signals = ["but also", "however", "on the other hand", "conversely"]
    contra_count = sum(1 for c in contradiction_signals if c in text_lower)
    scores["consistency"] = max(0, 100 - contra_count * 25)

    scope_signals = ["in-scope", "out-of-scope", "non-goal", "scope", "boundary"]
    scores["scope_boundary"] = min(
        100,
        sum(25 for s in scope_signals if s in text_lower),
    )

    return scores


def _judge_with_llm(spec_text: str, judge: Any) -> dict[str, int]:
    """LLM-based scoring — delegates to the judge client."""
    prompt = (
        "Score this specification on 5 dimensions (0-100 each):\n"
        f"1. completeness: {RUBRIC_DIMENSIONS['completeness']}\n"
        f"2. testability: {RUBRIC_DIMENSIONS['testability']}\n"
        f"3. unambiguity: {RUBRIC_DIMENSIONS['unambiguity']}\n"
        f"4. consistency: {RUBRIC_DIMENSIONS['consistency']}\n"
        f"5. scope_boundary: {RUBRIC_DIMENSIONS['scope_boundary']}\n\n"
        f"Spec:\n{spec_text[:5000]}\n\n"
        "Return JSON: {\"completeness\": N, \"testability\": N, ...}"
    )
    try:
        import json
        raw = judge.judge("Score spec quality", prompt, "claude-sonnet-4-6")
        data = json.loads(raw)
        if isinstance(data, dict):
            return {
                dim: min(100, max(0, int(data.get(dim, 50))))
                for dim in RUBRIC_DIMENSIONS
            }
    except Exception:  # noqa: BLE001
        pass
    return _heuristic_score(spec_text)
