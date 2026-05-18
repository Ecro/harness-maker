"""EIG (Expected Information Gain) scoring for the 5-term inequality gate.

Per PLAN-deep-interview-question-criteria ADR-002:
- Public signature `score_eig(q, ctx) -> float` is mechanism-agnostic.
- Default mechanism: LLM self-report proxy ("if user answered Q, would the
  implementation plan change? rate 0.0-1.0"). Real LLM call lives in F6
  (interview integration); F3 ships the injection point.
- Rollback path (Phase 3 exit): swap mechanism internally without touching
  callers — verified by test_eig_interface_stability.

ADR-007: default ε = 0.5; caller filters candidate Qs by EIG >= ε.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ADR-007: default EIG threshold. Caller (inequality_gate, F4) reads the
# actual value from harness.yaml.interview.deep_gate.eig_epsilon.
DEFAULT_EIG_EPSILON = 0.5


@dataclass(frozen=True)
class ScoringContext:
    """Frozen snapshot of interview state used for EIG scoring.

    `context_summary` is a short caller-produced string (≤ 500 chars
    recommended) summarizing the current plan state, ADRs, and remaining
    slots. The EIG cache is keyed by (q, context_summary) so the same Q
    under a different state is recomputed.
    """

    context_summary: str
    locale: str = "en"
    extras: dict[str, Any] | None = None


# Mechanism callable contract (mocked in tests).
# Signature: (q, ctx) -> confidence in [0.0, 1.0]. Internal — not exported.
EIGMechanism = Callable[[str, "ScoringContext"], float]


# Module-private cache. Hash-keyed by (q_hash, ctx_summary_hash) to keep
# memory bounded; collisions are theoretically possible but the 16-hex-char
# truncation gives 2^64 namespace which is overkill for an interview cache.
_cache: dict[tuple[str, str], float] = {}


def score_eig(
    q: str,
    ctx: ScoringContext,
    *,
    mechanism: EIGMechanism | None = None,
) -> float:
    """Return EIG score in [0.0, 1.0] for candidate question `q` under `ctx`.

    Mechanism-agnostic public signature (ADR-002). The default mechanism is
    LLM self-report proxy; tests inject a deterministic mock via `mechanism`.

    Cache: hash-keyed by (q, ctx.context_summary). Same (q, ctx) returns the
    cached score without re-invoking the mechanism. Process-lifetime cache;
    clear via `clear_eig_cache()` for test isolation.

    Args:
      q: Candidate interview question text.
      ctx: Frozen ScoringContext (caller-produced summary + locale).
      mechanism: Optional callable override; default uses the F6-wired
        LLM self-report proxy.

    Returns:
      Clamped score in [0.0, 1.0]. Non-numeric mechanism returns are
      treated as 0.0 with a warning log.
    """
    key = _cache_key(q, ctx)
    if key in _cache:
        return _cache[key]
    if mechanism is None:
        mechanism = _default_self_report_proxy
    try:
        raw = mechanism(q, ctx)
        score = float(raw)
    except (TypeError, ValueError) as exc:
        logger.warning(
            "score_eig: mechanism returned non-numeric for %r — treated as 0.0 (%s)",
            q,
            exc,
        )
        score = 0.0
    score = max(0.0, min(1.0, score))
    _cache[key] = score
    return score


def clear_eig_cache() -> None:
    """Reset the in-process EIG cache (test isolation helper)."""
    _cache.clear()


def cache_size() -> int:
    """Return current cache entry count (telemetry / test introspection)."""
    return len(_cache)


def _cache_key(q: str, ctx: ScoringContext) -> tuple[str, str]:
    """Hash-key from (q, ctx.context_summary).

    Truncated SHA-256 hex (16 chars each) keeps the namespace at 2^64 per
    side which is overkill for an interview cache. Truncation is acceptable
    because cache misses just re-invoke the mechanism — there's no security
    boundary at the hash.
    """
    q_hash = hashlib.sha256(q.encode("utf-8")).hexdigest()[:16]
    ctx_hash = hashlib.sha256(ctx.context_summary.encode("utf-8")).hexdigest()[:16]
    return (q_hash, ctx_hash)


def _default_self_report_proxy(q: str, ctx: ScoringContext) -> float:
    """ADR-002 default mechanism: 1-LLM-call self-report proxy.

    Real implementation lives in F6 (interview integration); F3 ships the
    injection point. When invoked without a mechanism override in tests,
    this raises NotImplementedError to surface the missing wiring loudly.
    """
    raise NotImplementedError(
        "score_eig default mechanism (LLM self-report proxy) is wired in F6. "
        f"Tests must supply mechanism= argument (q={q!r}, locale={ctx.locale!r})."
    )
