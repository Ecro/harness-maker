"""Unit tests for eig.score_eig (PLAN F3)."""

from __future__ import annotations

from typing import Any

import pytest

from harness_maker.eig import (
    DEFAULT_EIG_EPSILON,
    ScoringContext,
    cache_size,
    clear_eig_cache,
    score_eig,
)


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """Clear EIG cache before each test for isolation."""
    clear_eig_cache()


def _ctx(summary: str = "test ctx", locale: str = "en") -> ScoringContext:
    return ScoringContext(context_summary=summary, locale=locale)


# ---------- Score range + clamping -----------------------------------------------------


def test_mechanism_value_returned_as_is() -> None:
    """A mock returning 0.7 yields 0.7."""
    score = score_eig("Q?", _ctx(), mechanism=lambda q, c: 0.7)
    assert score == 0.7


def test_score_clamped_below_zero() -> None:
    """Negative mechanism return is clamped to 0.0."""
    assert score_eig("Q", _ctx(), mechanism=lambda q, c: -1.5) == 0.0


def test_score_clamped_above_one() -> None:
    """Mechanism return >1.0 is clamped to 1.0."""
    assert score_eig("Q", _ctx(), mechanism=lambda q, c: 1.7) == 1.0


def test_non_numeric_mechanism_returns_zero() -> None:
    """Non-numeric mechanism return is defensively treated as 0.0."""

    def bad(q: str, ctx: ScoringContext) -> float:
        return "not a number"  # type: ignore[return-value]

    assert score_eig("Q", _ctx(), mechanism=bad) == 0.0


# ---------- Cache semantics ------------------------------------------------------------


def test_cache_hit_skips_mechanism() -> None:
    """A repeated (q, ctx) call hits the cache without re-invoking the mechanism."""
    calls: list[tuple[str, str]] = []

    def counting(q: str, ctx: ScoringContext) -> float:
        calls.append((q, ctx.context_summary))
        return 0.42

    ctx = _ctx("state-A")
    s1 = score_eig("Q?", ctx, mechanism=counting)
    s2 = score_eig("Q?", ctx, mechanism=counting)
    assert s1 == s2 == 0.42
    assert len(calls) == 1, "second call must come from cache"


def test_cache_distinguishes_by_question() -> None:
    """Different `q` values produce separate cache entries."""
    calls: list[str] = []

    def counting(q: str, ctx: ScoringContext) -> float:
        calls.append(q)
        return 0.5

    score_eig("Q-A?", _ctx("state"), mechanism=counting)
    score_eig("Q-B?", _ctx("state"), mechanism=counting)
    assert len(calls) == 2
    assert cache_size() == 2


def test_cache_distinguishes_by_context_summary() -> None:
    """Different ctx.context_summary values produce separate cache entries."""
    calls: list[str] = []

    def counting(q: str, ctx: ScoringContext) -> float:
        calls.append(ctx.context_summary)
        return 0.5

    score_eig("Q?", _ctx("state-1"), mechanism=counting)
    score_eig("Q?", _ctx("state-2"), mechanism=counting)
    assert calls == ["state-1", "state-2"]


def test_clear_cache_resets_size_to_zero() -> None:
    """clear_eig_cache empties the cache."""
    score_eig("Q?", _ctx(), mechanism=lambda q, c: 0.5)
    assert cache_size() == 1
    clear_eig_cache()
    assert cache_size() == 0


# ---------- ε threshold boundary -------------------------------------------------------


def test_default_epsilon_is_0_5() -> None:
    """Sentinel: DEFAULT_EIG_EPSILON matches ADR-007."""
    assert DEFAULT_EIG_EPSILON == 0.5


def test_epsilon_inclusive_boundary_at_caller() -> None:
    """score_eig itself doesn't enforce ε — filter happens in F4 (inequality_gate).

    This test just pins the contract: scoring returns the raw clamped float;
    the gate decides ask/skip via `score >= DEFAULT_EIG_EPSILON`.
    """
    score = score_eig("Q?", _ctx(), mechanism=lambda q, c: 0.5)
    assert score >= DEFAULT_EIG_EPSILON  # boundary: 0.5 is included


def test_epsilon_below_boundary() -> None:
    """A score < ε would be filtered out by the gate (caller-side check)."""
    score = score_eig("Q?", _ctx(), mechanism=lambda q, c: 0.49)
    assert score < DEFAULT_EIG_EPSILON


# ---------- Default mechanism behavior -------------------------------------------------


def test_default_mechanism_raises_not_implemented() -> None:
    """No mechanism + no F6 wiring → loud NotImplementedError, not a silent 0.0."""
    with pytest.raises(NotImplementedError, match="wired in F6"):
        score_eig("Q?", _ctx())


# ---------- ScoringContext shape -------------------------------------------------------


def test_scoring_context_immutable() -> None:
    """ScoringContext is frozen (dataclass(frozen=True))."""
    ctx = _ctx()
    # FrozenInstanceError inherits from AttributeError in Python 3.11+.
    with pytest.raises(AttributeError):
        ctx.locale = "ko"  # type: ignore[misc]


def test_scoring_context_defaults() -> None:
    """ScoringContext requires only context_summary; locale defaults to 'en'."""
    ctx = ScoringContext(context_summary="just summary")
    assert ctx.locale == "en"
    assert ctx.extras is None


def test_scoring_context_extras_optional() -> None:
    """ScoringContext.extras accepts arbitrary metadata."""
    ctx = ScoringContext(context_summary="x", extras={"slot": "DB", "round": 2})
    assert ctx.extras == {"slot": "DB", "round": 2}


# ---------- Caching does NOT leak across mechanisms (mechanism is not part of key) -----


def test_cache_ignores_mechanism_identity() -> None:
    """The cache key is (q, ctx_summary) only — mechanism swap returns cached value.

    This is intentional: the cache models the assumption that for a given
    (q, ctx) pair, EIG is a function of input alone. If a caller wants
    fresh recomputation, they call clear_eig_cache() first.
    """

    def m1(q: str, ctx: ScoringContext) -> float:
        return 0.3

    def m2(q: str, ctx: ScoringContext) -> float:
        return 0.9

    s1 = score_eig("Q?", _ctx(), mechanism=m1)
    s2 = score_eig("Q?", _ctx(), mechanism=m2)
    assert s1 == s2 == 0.3, "second call returned cached m1 result"


# ---------- Return value annotations ---------------------------------------------------


def test_return_type_is_float() -> None:
    """score_eig returns a plain float (not bool, not int, not numpy)."""
    result = score_eig("Q?", _ctx(), mechanism=lambda q, c: 0.5)
    assert type(result) is float


# ---------- Realistic mock LLM behavior ------------------------------------------------


def test_realistic_self_report_pattern() -> None:
    """Demonstrate the expected self-report shape: high for novel slots, low for known."""

    def realistic_self_report(q: str, ctx: ScoringContext) -> float:
        # Mock pattern: if Q asks about something already in ctx_summary, low EIG.
        if q.lower().split()[0] in ctx.context_summary.lower():
            return 0.2
        return 0.8

    ctx = _ctx("plan locks database engine to postgres; locale en")
    novel = score_eig("MQTT topic format?", ctx, mechanism=realistic_self_report)
    known = score_eig("database engine choice?", ctx, mechanism=realistic_self_report)
    assert novel > known
    assert novel >= DEFAULT_EIG_EPSILON
    assert known < DEFAULT_EIG_EPSILON


def test_locale_passed_through_context() -> None:
    """The mechanism receives ctx.locale and can adapt scoring.

    NOTE: cache key is (q, ctx.context_summary) — locale is NOT part of the key
    by design (see test_extras_does_not_affect_cache_key). So we vary q to
    force separate cache entries while changing locale.
    """

    def locale_aware(q: str, ctx: ScoringContext) -> float:
        return 0.9 if ctx.locale == "ko" else 0.4

    assert score_eig("Q-ko?", _ctx(locale="ko"), mechanism=locale_aware) == 0.9
    assert score_eig("Q-en?", _ctx(locale="en"), mechanism=locale_aware) == 0.4


def test_extras_passed_through_context() -> None:
    """The mechanism can read ctx.extras for richer signals."""

    def extras_aware(q: str, ctx: ScoringContext) -> float:
        if ctx.extras and ctx.extras.get("slot_priority") == "high":
            return 0.95
        return 0.3

    high = ScoringContext(context_summary="x", extras={"slot_priority": "high"})
    low = ScoringContext(context_summary="x")
    assert score_eig("Q?", high, mechanism=extras_aware) == 0.95
    # Same (q, ctx_summary) means cache hit for the second call — so we change q.
    assert score_eig("Q2?", low, mechanism=extras_aware) == 0.3


# ---------- Implementation detail: cache key derivation --------------------------------


def test_unicode_q_does_not_break_cache() -> None:
    """Cache key derivation handles non-ASCII question text."""
    score = score_eig("어떤 DB 를 쓸까요?", _ctx(), mechanism=lambda q, c: 0.6)
    assert score == 0.6
    assert cache_size() == 1


def test_extras_does_not_affect_cache_key() -> None:
    """Cache key is (q, ctx.context_summary) — extras and locale are NOT part of key.

    This matches the ADR-002 mechanism contract: for cache correctness, the
    mechanism should NOT depend on locale/extras to produce different scores
    for the same (q, summary). If it does, caller must encode that into
    context_summary.
    """
    calls: list[Any] = []

    def m(q: str, ctx: ScoringContext) -> float:
        calls.append(ctx.locale)
        return 0.5

    score_eig("Q?", ScoringContext(context_summary="x", locale="en"), mechanism=m)
    score_eig("Q?", ScoringContext(context_summary="x", locale="ko"), mechanism=m)
    # The second call hit the cache (same q + same summary), so m was called once.
    assert len(calls) == 1
