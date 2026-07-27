"""Phase 5 contract: cache diagnostics re-pointed at the transcript reader.

Before this phase Layer 3 was INERT, not wrong: `cache_diagnostics` skipped every
all-zero telemetry entry before classification, so `diagnose_cache` always returned
`no_data` / score 50 and `improvement` emitted no action. These tests pin the new core
against fixtures so the gate is CI-runnable — no test reads the real `~/.claude`.

Line-level malformation (truncated JSON, unknown keys, missing `usage`) is NOT owned
here: `TurnRecord` is `strict=True, extra="forbid"`, so a malformed line can never reach
this layer. `tests/unit/test_economics_source.py` owns that boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from harness_maker.cache_diagnostics import diagnose_cache_from_turns
from harness_maker.economics import TokenUsage, TurnRecord

_T0 = datetime(2026, 7, 25, 12, 0, 0, tzinfo=UTC)


def _turn(
    idx: int,
    usage: TokenUsage,
    *,
    minutes: float | None = None,
    model: str | None = "claude-opus-5",
) -> TurnRecord:
    return TurnRecord(
        session_id="s1",
        ts=_T0 + timedelta(minutes=minutes if minutes is not None else idx),
        model=model,
        usage=usage,
    )


def _hits(n: int, *, start: int = 0) -> list[TurnRecord]:
    return [
        _turn(start + i, TokenUsage(input_tokens=10, cache_read_tokens=5_000, output_tokens=50))
        for i in range(n)
    ]


# ---------------------------------------------------------------- the old baseline


def test_all_zero_usage_reproduces_the_pre_migration_no_data_result() -> None:
    """The exact behaviour the old path always returned, now pinned as a property."""
    turns = [_turn(i, TokenUsage()) for i in range(5)]
    d = diagnose_cache_from_turns(turns, model="opus")
    assert d.primary_failure == "no_data"
    assert d.score == 50
    assert d.sample_size == 0
    assert d.hit_rate == 0


def test_an_empty_window_is_no_data_not_a_crash() -> None:
    d = diagnose_cache_from_turns([], model="opus")
    assert d.primary_failure == "no_data"
    assert d.sample_size == 0


# ---------------------------------------------------------------- real signal


def test_all_hits_produce_a_full_hit_rate_and_no_primary_failure() -> None:
    d = diagnose_cache_from_turns(_hits(10), model="opus")
    assert d.hit_rate == 100
    assert d.score == 100
    assert d.sample_size == 10
    assert d.primary_failure is None
    assert d.counters["hit"] == 10


def test_hit_rate_is_the_pinned_ratio_for_a_mixed_window() -> None:
    # 6 hits + 4 sub-threshold misses -> 60%
    turns = _hits(6) + [_turn(6 + i, TokenUsage(input_tokens=10)) for i in range(4)]
    d = diagnose_cache_from_turns(turns, model="opus")
    assert d.sample_size == 10
    assert d.hit_rate == 60
    assert d.counters["hit"] == 6
    assert d.primary_failure == "miss_min_threshold"


def test_cache_creation_only_turns_are_classified_as_writes_not_sub_threshold() -> None:
    """`miss_min_threshold == 0` is the DISCRIMINATING assertion.

    `TokenUsage` carries two cache-write tier fields while `_classify_turn` reads a
    single differently-named key, so the likely mapping bug drops the creation signal
    entirely — which would reclassify these turns as sub-threshold misses and emit the
    wrong remediation. Asserting only `hit == 0` would pass in that broken world.
    """
    turns = [_turn(i, TokenUsage(input_tokens=10, cache_write_5m_tokens=4_000)) for i in range(4)]
    d = diagnose_cache_from_turns(turns, model="opus")
    assert d.sample_size == 4
    assert d.counters["hit"] == 0
    assert d.counters["miss_min_threshold"] == 0
    assert d.counters["miss_first"] == 1
    assert d.counters["miss_invalidation"] == 3


def test_both_cache_write_tiers_reach_the_creation_signal() -> None:
    """Pinned per tier — a symmetry-only assertion passes when BOTH tiers are dropped."""
    for usage in (
        TokenUsage(input_tokens=10, cache_write_5m_tokens=4_000),
        TokenUsage(input_tokens=10, cache_write_1h_tokens=4_000),
        TokenUsage(input_tokens=10, cache_write_5m_tokens=2_000, cache_write_1h_tokens=2_000),
    ):
        d = diagnose_cache_from_turns([_turn(0, usage)], model="opus")
        assert d.counters["miss_first"] == 1
        assert d.counters["miss_min_threshold"] == 0


def test_a_long_gap_is_classified_as_a_ttl_miss() -> None:
    """Also guards the datetime-vs-str trap: `_parse_timestamp` needs an ISO string,
    but `TurnRecord.ts` is a datetime — a naive model_dump bridge silently yields
    `miss_invalidation` here instead."""
    turns = [
        _turn(0, TokenUsage(input_tokens=10, cache_read_tokens=5_000), minutes=0),
        _turn(1, TokenUsage(input_tokens=5_000, cache_write_5m_tokens=5_000), minutes=30),
    ]
    d = diagnose_cache_from_turns(turns, model="opus")
    assert d.counters["miss_ttl"] == 1
    assert d.primary_failure == "miss_ttl"


# ---------------------------------------------------------------- threshold semantics


def test_the_threshold_comes_from_the_turns_model_not_the_window_model() -> None:
    """INVERTED by PLAN ADR-012 — this used to assert the window-level semantics.

    The retired version pinned the opposite outcome and said so explicitly: "an
    implementation that derived the threshold per-turn from `turn.model` would score
    it as one". That semantics is the defect, not the contract. The published minimum
    is non-monotonic within a family (Opus 5 = 512, Opus 4.6 = 4096), so one threshold
    per window cannot be correct for a mixed window; and every production caller passed
    a hard-coded string, so the table was never applied to real data at all.

    The fixture is unchanged and still straddles: 2_000 tokens is above a 1024 minimum
    and below haiku's 4096. `model=` is now only a FALLBACK for turns with no model of
    their own, so the turn's own `claude-haiku-4-5` wins and it IS a sub-threshold miss.
    """
    turns = [
        _turn(0, TokenUsage(input_tokens=2_000), model="claude-haiku-4-5-20251001"),
        *_hits(3, start=1),
    ]
    d = diagnose_cache_from_turns(turns, model="claude-opus-4-8")
    assert d.sample_size == 4
    assert d.hit_rate == 75
    assert d.counters["miss_min_threshold"] == 1
    assert d.counters["miss_first"] == 0


def test_a_turn_with_no_model_does_not_crash_the_window() -> None:
    """`TurnRecord.model` is optional — the absent case must be inert, not fatal."""
    turns = [_turn(0, TokenUsage(input_tokens=10, cache_read_tokens=5_000), model=None)]
    d = diagnose_cache_from_turns(turns, model="opus")
    assert d.sample_size == 1
    assert d.hit_rate == 100


def test_a_degenerate_but_valid_turn_is_inert_rather_than_raising() -> None:
    """The S6 'malformed' case as it can actually reach this layer."""
    d = diagnose_cache_from_turns([_turn(0, TokenUsage(), model=None)], model="opus")
    assert d.primary_failure == "no_data"
    assert d.sample_size == 0


# ---------------------------------------------------------------- window semantics


def test_window_turns_caps_the_sample_and_takes_the_most_recent() -> None:
    """`window_turns` is an explicit TURN COUNT — the old `window` did double duty
    as a day-based file selector and an entry cap with one default of 50."""
    misses = [_turn(i, TokenUsage(input_tokens=10)) for i in range(10)]
    recent_hits = _hits(5, start=10)
    d = diagnose_cache_from_turns(misses + recent_hits, model="opus", window_turns=5)
    assert d.sample_size == 5
    assert d.hit_rate == 100


def test_the_capped_window_stays_in_chronological_order() -> None:
    """TTL math depends on ordering; a cap that reversed the slice would count 0 or 2
    TTL misses here instead of 1."""
    turns = [
        *_hits(3, start=0),
        _turn(3, TokenUsage(input_tokens=10, cache_read_tokens=5_000), minutes=3),
        _turn(4, TokenUsage(input_tokens=5_000, cache_write_5m_tokens=5_000), minutes=40),
        _turn(5, TokenUsage(input_tokens=5_000, cache_write_5m_tokens=5_000), minutes=41),
    ]
    d = diagnose_cache_from_turns(turns, model="opus", window_turns=3)
    assert d.sample_size == 3
    assert d.counters["miss_ttl"] == 1


def test_window_turns_larger_than_the_input_uses_everything() -> None:
    d = diagnose_cache_from_turns(_hits(3), model="opus", window_turns=1000)
    assert d.sample_size == 3


# ---------------------------------------------------------------- the old symbol is gone


def test_the_path_taking_diagnose_cache_and_its_io_path_are_both_gone() -> None:
    """Retaining it would be a second phantom-data path: once telemetry stops writing
    the token fields, it returns `no_data` unconditionally, forever. The `_metrics_io`
    assertion pins the deleted I/O path, not just the name (a rename would slip past
    a bare hasattr check)."""
    import harness_maker.cache_diagnostics as cd

    assert not hasattr(cd, "diagnose_cache")
    source = __import__("pathlib").Path(cd.__file__).read_text(encoding="utf-8")
    assert "_metrics_io" not in source
    assert "iter_recent_entries" not in source


def test_diagnosis_is_serialisable_for_the_ai_readiness_deserialization_contract() -> None:
    """`ai_readiness.finalize_from_verdicts_json` re-validates a dumped CacheDiagnosis."""
    from harness_maker.cache_diagnostics import CacheDiagnosis

    dumped = diagnose_cache_from_turns(_hits(4), model="opus").model_dump(mode="json")
    assert CacheDiagnosis.model_validate(dumped).hit_rate == 100


# ---------------------------------------------------------------- TTL regression
# Ported from the removed diagnose_cache(path) I/O tests — behaviour worth keeping,
# now exercised through the pure core instead of through a metrics file.


def _ttl_window(early_gap: float, late_gap: float, n: int = 20) -> list[TurnRecord]:
    """Half the window at `early_gap` minutes between turns, half at `late_gap`."""
    turns: list[TurnRecord] = []
    clock = 0.0
    for i in range(n):
        clock += early_gap if i < n // 2 else late_gap
        turns.append(
            _turn(i, TokenUsage(input_tokens=5_000, cache_write_5m_tokens=5_000), minutes=clock)
        )
    return turns


def test_ttl_regression_is_detected_when_gaps_widen_late_in_the_window() -> None:
    d = diagnose_cache_from_turns(_ttl_window(early_gap=1.0, late_gap=30.0), model="opus")
    assert d.ttl_regression is True
    assert "TTL miss rate increased" in d.ttl_regression_detail


def test_no_ttl_regression_when_gaps_are_consistent() -> None:
    d = diagnose_cache_from_turns(_ttl_window(early_gap=1.0, late_gap=1.0), model="opus")
    assert d.ttl_regression is False
    assert d.ttl_regression_detail == ""


def test_ttl_regression_needs_a_minimum_window() -> None:
    """Under 10 entries the comparison is noise, so it must not fire."""
    d = diagnose_cache_from_turns(_ttl_window(early_gap=1.0, late_gap=30.0, n=6), model="opus")
    assert d.ttl_regression is False
