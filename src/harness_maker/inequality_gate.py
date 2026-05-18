"""5-term inequality gate composition for the deep-interview system (0.16.0).

Per PLAN-deep-interview-question-criteria:
- ADR-001: composes
    ask(Q) iff EIG(Q) >= ε
            ∧ TaskRel·UserAns >= 0.7
            ∧ slot ∉ common_ground
            ∧ confidence < τ
            ∧ open_ended < cap_locale
- ADR-005: per-candidate 5-term checklist available for UI render
  ("✅ EIG ✅ CLARITI ❌ common-ground ✅ confidence ✅ open-ended → 4/5 met").
- ADR-007: locale-aware open_ended cap.

Apply the gate to a list of candidate questions; receive a list of GateResult
ordered passes-first, by descending EIG. Tests inject mock mechanisms via
`eig_mechanism` / `cg_llm_fn`; F6 wires the real LLM-backed ones.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from harness_maker.common_ground import CGMark, detect_common_ground
from harness_maker.eig import EIGMechanism, ScoringContext, score_eig


@dataclass(frozen=True)
class Candidate:
    """An interview-question candidate evaluated by the gate.

    Caller pre-populates `task_relevance` / `user_answerability` (CLARITI
    factors) and `confidence` (the slot-resolution confidence already
    accumulated from prior rounds). `is_open_ended` flags free-form Qs
    which the locale cap restricts.
    """

    slot: str
    question: str
    task_relevance: float = 1.0
    user_answerability: float = 1.0
    is_open_ended: bool = False
    confidence: float = 0.0


@dataclass(frozen=True)
class GateResult:
    """5-term verdict for a single candidate (ADR-005 checklist render input)."""

    candidate: Candidate
    eig_pass: bool
    clariti_pass: bool
    not_common_ground_pass: bool
    confidence_pass: bool
    open_ended_pass: bool
    eig_score: float
    common_ground_mark: CGMark | None

    @property
    def overall_pass(self) -> bool:
        return (
            self.eig_pass
            and self.clariti_pass
            and self.not_common_ground_pass
            and self.confidence_pass
            and self.open_ended_pass
        )

    @property
    def passed_count(self) -> int:
        return sum(
            (
                self.eig_pass,
                self.clariti_pass,
                self.not_common_ground_pass,
                self.confidence_pass,
                self.open_ended_pass,
            )
        )

    @property
    def checklist_summary(self) -> str:
        """ADR-005 5-term checklist render."""

        def e(passes: bool) -> str:
            return "✅" if passes else "❌"

        terms = (
            ("EIG", self.eig_pass),
            ("CLARITI", self.clariti_pass),
            ("common-ground", self.not_common_ground_pass),
            ("confidence", self.confidence_pass),
            ("open-ended", self.open_ended_pass),
        )
        rendered = " ".join(f"{e(p)} {label}" for label, p in terms)
        verdict = "PASS" if self.overall_pass else "NEEDS"
        return f"{rendered} → {self.passed_count}/5 met ({verdict})"


@dataclass(frozen=True)
class GateConfig:
    """Gate runtime configuration (sourced from harness.yaml.interview.deep_gate)."""

    eig_epsilon: float = 0.5
    confidence_tau: float = 0.7
    open_ended_cap_by_locale: dict[str, int] = field(
        default_factory=lambda: {"en": 2, "ko": 1, "ja": 1, "default": 1}
    )
    clariti_threshold: float = 0.7
    llm_inference_enabled: bool = True
    llm_inference_threshold: float = 0.95

    def cap_for_locale(self, locale: str) -> int:
        return self.open_ended_cap_by_locale.get(
            locale, self.open_ended_cap_by_locale.get("default", 1)
        )


def apply_inequality_gate(
    candidates: list[Candidate],
    sources: dict[str, Any],
    config: GateConfig,
    *,
    eig_mechanism: EIGMechanism,
    locale: str = "en",
    cg_llm_fn: Callable[[str, dict[str, Any]], float] | None = None,
    context_summary: str = "",
    accumulator: list[CGMark] | None = None,
) -> list[GateResult]:
    """Apply the 5-term inequality to every candidate; return ALL with verdict.

    Returns the FULL list of GateResult (passes AND non-passes) so the caller
    can render the ADR-005 checklist for every candidate. Ordering:
      1. overall_pass=True first
      2. eig_score DESC (ties keep input order — Python sort is stable)

    Open-ended locale cap is enforced after sorting: among `overall_pass=True`
    open-ended candidates, only the first `cap_for_locale(locale)` keep
    `open_ended_pass=True`; subsequent ones are demoted (`open_ended_pass=False`,
    `overall_pass=False`).
    """
    ctx = ScoringContext(context_summary=context_summary, locale=locale)
    cap = config.cap_for_locale(locale)

    results: list[GateResult] = []
    for c in candidates:
        eig = score_eig(c.question, ctx, mechanism=eig_mechanism)
        eig_pass = eig >= config.eig_epsilon

        clariti_score = c.task_relevance * c.user_answerability
        clariti_pass = clariti_score >= config.clariti_threshold

        cg_mark = detect_common_ground(
            c.slot,
            sources,
            llm_inference_enabled=config.llm_inference_enabled,
            llm_inference_threshold=config.llm_inference_threshold,
            llm_inference_fn=cg_llm_fn,
            accumulator=accumulator,
        )
        not_common_ground_pass = cg_mark is None

        confidence_pass = c.confidence < config.confidence_tau

        # Provisional: open-ended is allowed until cap-enforcement below.
        results.append(
            GateResult(
                candidate=c,
                eig_pass=eig_pass,
                clariti_pass=clariti_pass,
                not_common_ground_pass=not_common_ground_pass,
                confidence_pass=confidence_pass,
                open_ended_pass=True,
                eig_score=eig,
                common_ground_mark=cg_mark,
            )
        )

    # Sort: passes first, then EIG descending. Stable sort preserves input order on ties.
    results.sort(key=lambda r: (not _provisional_overall(r), -r.eig_score))

    # Enforce locale open-ended cap on the sorted passes.
    open_ended_seen = 0
    capped: list[GateResult] = []
    for r in results:
        if _provisional_overall(r) and r.candidate.is_open_ended:
            if open_ended_seen >= cap:
                capped.append(replace(r, open_ended_pass=False))
                continue
            open_ended_seen += 1
        capped.append(r)
    # Re-sort post-demotion to restore the "passes first" docstring guarantee.
    # Without this, a cap-demoted open-ended candidate (now overall_pass=False)
    # would sit BEFORE a lower-EIG closed candidate that's still passing,
    # breaking the contract F6 relies on for "ask candidates from index 0
    # until overall_pass goes False".
    capped.sort(key=lambda r: (not r.overall_pass, -r.eig_score))
    return capped


def _provisional_overall(r: GateResult) -> bool:
    """True iff all terms pass EXCEPT the cap-affected open_ended check.

    Used by the cap-enforcement step to identify "would-be passes that are
    only blocked by the open-ended quota" — they're the candidates the cap
    is meant to ration.
    """
    return r.eig_pass and r.clariti_pass and r.not_common_ground_pass and r.confidence_pass
