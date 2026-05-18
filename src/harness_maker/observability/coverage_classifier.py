"""Post-hoc coverage-kind classifier for the deep-interview gate (ADR-010)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Literal, get_args

logger = logging.getLogger(__name__)

CoverageKind = Literal["WRONG", "METHOD", "STAKEHOLDER", "STYLE", "PERF", "OTHER"]

# Derived from the Literal so adding a new kind only requires editing one place.
ALL_KINDS: frozenset[str] = frozenset(get_args(CoverageKind))

# Heuristic substring → kind map used in CI / synthetic fixtures only.
# Production wiring supplies an LLM `classifier_fn`; this fallback exists so
# unit tests run deterministically. Order matters: earlier entries win on
# overlap (e.g. "review" hits STAKEHOLDER before STYLE could match elsewhere).
# Substrings with leading/trailing spaces avoid prefix collisions
# (e.g. " scale " avoids matching "rescale" / "downscale").
_HEURISTIC_MAP: tuple[tuple[tuple[str, ...], CoverageKind], ...] = (
    (("wrong", "fail", "rejection criteria"), "WRONG"),
    (("how will", "assumption", " method ", "implement"), "METHOD"),
    (("stakeholder", "review", "audience", "approve"), "STAKEHOLDER"),
    (("format", "style", " convention", "naming"), "STYLE"),
    (("performance", " scale ", "throughput", "latency"), "PERF"),
)


# Public type alias for the LLM classifier callable (mocked in tests).
ClassifierFn = Callable[[str], CoverageKind]


def classify_q(
    asked_q: str,
    *,
    classifier_fn: ClassifierFn | None = None,
) -> CoverageKind:
    """Classify post-hoc to feed ADR-010 telemetry — not used in the gate decision itself."""
    if classifier_fn is not None:
        result = classifier_fn(asked_q)
        if result not in ALL_KINDS:
            logger.warning(
                "coverage_classifier: classifier_fn returned unknown kind %r "
                "for q %r — coerced to OTHER",
                result,
                asked_q[:50],
            )
            return "OTHER"
        return result

    q_lower = asked_q.lower()
    for substrings, kind in _HEURISTIC_MAP:
        if any(s in q_lower for s in substrings):
            return kind
    return "OTHER"
