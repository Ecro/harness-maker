"""AC-001/002/004 + ADR-012 boundary rules — asserted through the production path.

Every assertion here names the specific wrong implementation it rejects, per
`[fail:test] assertion-invariant-over-named-dimension` (count:3). The recurring
defect in this area is an assertion that is invariant over the dimension its name
claims to cover; the discriminating fixture values below are the point of the file.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker.cache_diagnostics import _MIN_CACHEABLE_PREFIX, diagnose_cache_from_turns
from harness_maker.economics import TokenUsage, TurnRecord
from harness_maker.spec_machine import GoldenRow, load_golden_table

_SPEC = Path(__file__).parents[2] / "specs" / "SPEC-token-economy-step-pruning.machine.yaml"
_BASE = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def _turn(
    *,
    model: str | None,
    prefix: int = 0,
    read: int = 0,
    w5m: int = 0,
    w1h: int = 0,
    offset_s: int = 0,
    session: str = "s1",
) -> TurnRecord:
    return TurnRecord(
        session_id=session,
        ts=_BASE + timedelta(seconds=offset_s),
        model=model,
        usage=TokenUsage(
            input_tokens=prefix,
            output_tokens=1,
            cache_read_tokens=read,
            cache_write_5m_tokens=w5m,
            cache_write_1h_tokens=w1h,
        ),
    )


# ── AC-001 — per-model minimums, non-monotonic, through the production path ──

_ROWS = load_golden_table(_SPEC, "AC-001")


@pytest.mark.parametrize(
    "row",
    _ROWS,
    ids=[str(r.input["turn_model"]) for r in _ROWS],
)
def test_min_cacheable_is_per_model_and_non_monotonic(row: GoldenRow) -> None:
    """Each row is driven through `diagnose_cache_from_turns`, not the resolver.

    Rejects: a correct `_threshold_for_model` whose value never reaches the
    classifier because `_entry_from_turn` drops `model` (the pass-1 C1 defect).
    The probe is a two-turn window straddling the row's expected minimum — the
    turn one token BELOW it must be sub-threshold and the turn AT it must not,
    so the assertion pins the boundary rather than a bound.
    """
    model = str(row.input["turn_model"])
    expected = int(row.expected)

    below = diagnose_cache_from_turns([_turn(model=model, prefix=expected - 1)])
    at = diagnose_cache_from_turns([_turn(model=model, prefix=expected)])

    assert below.counters["miss_min_threshold"] == 1, (
        f"{model}: a prefix of {expected - 1} must be below the {expected} minimum"
    )
    assert at.counters["miss_min_threshold"] == 0, (
        f"{model}: a prefix of {expected} must NOT be below the {expected} minimum"
    )


def test_mixed_model_window_resolves_two_thresholds() -> None:
    """One window, two models, two different applied minimums.

    Rejects: any window-level threshold resolution. With a single threshold — no
    matter which value it picks — the two turns below cannot both be classified
    as the per-model contract requires, because 700 straddles opus-5 (512) and
    opus-4-6 (4096) in opposite directions.
    """
    diag = diagnose_cache_from_turns(
        [
            _turn(model="claude-opus-5", prefix=700, offset_s=0),
            _turn(model="claude-opus-4-6", prefix=700, offset_s=10),
        ]
    )
    # opus-5: 700 >= 512 → not sub-threshold. opus-4-6: 700 < 4096 → sub-threshold.
    assert diag.counters["miss_min_threshold"] == 1


# ── AC-002 — an unknown model never yields a guessed threshold verdict ───────


def test_unknown_model_never_min_threshold() -> None:
    """Three arms, each rejecting a different named implementation.

    Arm 1 (unknown, 100): a fallback to any positive default makes 100
    sub-threshold and emits the verdict — only a `None` threshold passes.
    Arm 2 (opus-4-6, 2000): the correct 4096 emits the verdict; a 1024 fallback
    does not, so the arm dies if `model` never reaches the classifier.
    Arm 3 (opus-5, 700): the correct 512 emits nothing; a 1024 fallback emits it.
    Arms 2 and 3 are opposite-signed on the same defect, so no single fallback
    value satisfies both.
    """
    unknown = diagnose_cache_from_turns([_turn(model="claude-not-a-real-model-9", prefix=100)])
    high = diagnose_cache_from_turns([_turn(model="claude-opus-4-6", prefix=2000)])
    low = diagnose_cache_from_turns([_turn(model="claude-opus-5", prefix=700)])

    assert unknown.counters["miss_min_threshold"] == 0
    assert high.counters["miss_min_threshold"] >= 1
    assert low.counters["miss_min_threshold"] == 0


def test_unknown_model_is_reported_not_silently_defaulted() -> None:
    """The absent case must be visible (CLAUDE.md absent-case rule, ADR-004).

    Rejects: silently skipping the sub-threshold test for an unknown model, which
    satisfies `test_unknown_model_never_min_threshold` while hiding that the
    diagnosis is degraded.

    The count is pinned EXACTLY. A `>= 1` arm was satisfied by an implementation that
    reported the first unknown turn and misclassified the rest, which is the
    `assertion-invariant-over-named-dimension` shape. Three turns 60s apart: turn 0 is
    the session's first (no prior cache could exist — `miss_first` regardless of what
    the minimum is), and turns 1-2 are inside the 5m tier and below no known minimum,
    so `miss_invalidation` would be a conclusion by elimination that an unknown minimum
    does not license — they are the two that must report as unknown.
    """
    diag = diagnose_cache_from_turns(
        [_turn(model="claude-not-a-real-model-9", prefix=100, offset_s=60 * i) for i in range(3)]
    )
    assert diag.counters["miss_unknown_model"] == 2
    assert diag.counters["miss_first"] == 1


# ── AC-004 — TTL tier attribution (ADR-005) ─────────────────────────────────


def _session_with_prior_write(tier: str, gap_seconds: int) -> list[TurnRecord]:
    w5m, w1h = (0, 5000) if tier == "1h" else (5000, 0)
    return [
        _turn(model="claude-sonnet-4-6", prefix=6000, w5m=w5m, w1h=w1h, offset_s=0),
        _turn(model="claude-sonnet-4-6", prefix=6000, w5m=1, offset_s=gap_seconds),
    ]


def test_one_hour_ttl_not_miss_ttl() -> None:
    """A 30-minute gap is a miss under the 5m tier and a hit-window under 1h.

    Rejects: the hard-coded `_TTL_SECONDS = 300`. Asserting only the 1h arm would
    pass against a classifier that never emits `miss_ttl` at all, so the 5m arm is
    load-bearing and the two are asserted together.
    """
    one_h = diagnose_cache_from_turns(_session_with_prior_write("1h", 1800))
    five_m = diagnose_cache_from_turns(_session_with_prior_write("5m", 1800))

    assert one_h.counters["miss_ttl"] == 0
    assert five_m.counters["miss_ttl"] == 1


def test_one_hour_tier_does_not_cross_session_boundary() -> None:
    """ADR-012 boundary rule 2 — the tier lookup is session-scoped.

    Rejects: taking the chronologically previous cache-writing entry regardless of
    `session_id`. `diagnose_cache_from_turns` flattens every session into one
    chronological list, so that implementation passes `test_one_hour_ttl_not_miss_ttl`
    and is wrong. Here the 1h write belongs to a DIFFERENT session, so the tier must
    not be inherited and the 30-minute gap is a 5m-tier miss.
    """
    turns = [
        _turn(model="claude-sonnet-4-6", prefix=6000, w1h=5000, offset_s=0, session="other"),
        _turn(model="claude-sonnet-4-6", prefix=6000, w5m=1, offset_s=1800, session="mine"),
    ]
    assert diagnose_cache_from_turns(turns).counters["miss_ttl"] == 1


# ── ADR-012 boundary rules 1 and 3 ──────────────────────────────────────────


def test_ttl_regression_not_manufactured_by_segment_split() -> None:
    """Boundary rule 1 — the prior-write lookup crosses the half-window split.

    The window is ONE 1h write followed by 15 turns spaced 30 min apart that write
    nothing of their own, so the only attributable prior write for every one of
    them is turn 0 — which sits in the first half. Under a correct cross-segment
    lookup the applicable tier is 3600s throughout and no gap is a miss.

    Rejects: a segment-local lookup. `_detect_ttl_regression` re-classifies each
    half; confined to a segment, the second half has no attributable write at all,
    falls back to ADR-005's 300s, and every 1800s gap becomes a miss — rate_early
    0.0 vs rate_recent ~0.9, which trips `rate_recent > rate_early + 0.15 and
    rate_recent > 0.2` and manufactures a regression along the exact axis the
    helper measures.

    The turns deliberately carry NO cache write of their own: an earlier draft gave
    each one `w5m=1`, which under ADR-005 makes turn i-1 the most recent
    cache-writing turn and the applicable tier 300s — so a CORRECT implementation
    would have produced 14 misses and the test could only have been satisfied by
    weakening ADR-005 to a session-sticky 1h rule.
    """
    turns = [_turn(model="claude-sonnet-4-6", prefix=6000, w1h=5000, offset_s=0)]
    turns += [
        _turn(model="claude-sonnet-4-6", prefix=6000, offset_s=1800 * (i + 1)) for i in range(15)
    ]
    diag = diagnose_cache_from_turns(turns)
    assert diag.counters["miss_ttl"] == 0
    assert diag.ttl_regression is False


def test_unknown_minimum_does_not_suppress_the_ttl_verdict() -> None:
    """Review finding — the unknown-minimum branch must not swallow unrelated tests.

    Rejects: returning `miss_unknown_model` from the threshold branch, ahead of the
    first-turn / TTL / invalidation branches. An unknown minimum says nothing about
    whether the gap outlived the cache, and `_detect_ttl_regression` counts only
    `miss_ttl`, so that ordering made TTL regression undetectable for the whole window.
    Here the model is unknown AND the 2h gap exceeded the 5m tier: the TTL verdict must
    still be reached.

    The second turn deliberately writes NOTHING. An earlier version gave it `w5m=1`,
    which made `creation_tok != 0` — and the unknown branch is creation-gated, so it
    could not fire in ANY ordering. The gate was invariant over the ordering it claims
    to pin: moving the unknown branch back to position 1 left both assertions holding.
    """
    turns = [
        _turn(model="claude-not-a-real-model-9", prefix=6000, w5m=5000, offset_s=0),
        _turn(model="claude-not-a-real-model-9", prefix=6000, offset_s=7200),
    ]
    diag = diagnose_cache_from_turns(turns)
    assert diag.counters["miss_ttl"] == 1
    assert diag.counters["miss_unknown_model"] == 0


def test_an_unknown_model_with_no_actionable_miss_does_not_crash() -> None:
    """A lone unknown-minimum turn yields no primary — and must not raise.

    Rejects: folding the unknown-minimum guard into the `not actionable` early return.
    A single unknown-model turn classifies `miss_first`, which is expected and therefore
    not actionable — so `actionable` is empty. A merged condition falls past the early
    return into `max(actionable, ...)` and raises `ValueError: max() iterable argument
    is empty`, turning `/hm:health` into a crash on any project whose window happens to
    hold one turn from an unrecognised model.

    The window reports no primary and "No action needed" — which is correct here and
    NOT concealment: the sole turn is the session's first, a cause that holds whatever
    the minimum is. `counters` still records the classification for anyone who wants it.
    """
    diag = diagnose_cache_from_turns([_turn(model="claude-not-a-real-model-9", prefix=100)])
    assert diag.primary_failure is None
    assert diag.counters["miss_first"] == 1


def test_an_assumed_tier_is_reported_as_assumed_not_as_measured() -> None:
    """An unknown model with no prior write must not yield a confident TTL claim.

    Nothing was ever cached in this session (no turn writes), so the tier is ASSUMED
    5m and every 10-minute gap becomes `miss_ttl`. That classification is defensible —
    but the evidence must say the tier was assumed rather than observed, or the user is
    told to "keep sessions tighter" on the strength of a number nobody measured.

    Rejects: dropping the `assumed_tier_turns` accounting, or emitting the miss_ttl
    branch without it. Every other unknown-model fixture in this file uses <= 60s
    spacing or an observed prior write, so none of them reaches this branch.
    """
    turns = [
        _turn(model="claude-not-a-real-model-9", prefix=6000, offset_s=600 * i) for i in range(3)
    ]
    diag = diagnose_cache_from_turns(turns)
    assert diag.primary_failure == "miss_ttl"
    assert diag.counters["miss_ttl"] == 2
    assert "assumed" in diag.evidence.lower()


def test_ttl_tier_survives_the_reporting_window_boundary() -> None:
    """Review finding — the tier lookup must see writes from before the window opens.

    Rejects: truncating the entry list to `window_turns` BEFORE classification. The 1h
    write sits at index 0 and the reporting window is the last 2 turns, so a truncating
    implementation loses it, falls back to the 5m default, and reports the 30-minute
    gap as a TTL miss for turns that were well inside their actual tier.
    """
    turns = [
        _turn(model="claude-sonnet-4-6", prefix=6000, w1h=5000, offset_s=0),
        _turn(model="claude-sonnet-4-6", prefix=6000, offset_s=1800),
        _turn(model="claude-sonnet-4-6", prefix=6000, offset_s=3600),
    ]
    diag = diagnose_cache_from_turns(turns, window_turns=2)
    assert diag.sample_size == 2
    assert diag.counters["miss_ttl"] == 0


def test_unidentifiable_session_does_not_inherit_a_tier() -> None:
    """Review finding — an empty `session_id` must not match every other empty one.

    `economics_source` emits `str(data.get("sessionId") or "")`, so turns with no
    sessionId all collapse to `""`. Rejects: a bare `!=` comparison, under which those
    turns compare EQUAL and borrow each other's 1h tier across unrelated sessions.
    """
    turns = [
        _turn(model="claude-sonnet-4-6", prefix=6000, w1h=5000, offset_s=0, session=""),
        _turn(model="claude-sonnet-4-6", prefix=6000, w5m=1, offset_s=1800, session=""),
    ]
    assert diagnose_cache_from_turns(turns).counters["miss_ttl"] == 1


def test_healthy_shortcut_does_not_hide_an_incomplete_diagnosis() -> None:
    """Review finding — "No action needed" must not be claimed on unmeasured turns.

    Rejects: the `hit_rate >= 80` early return firing while `miss_unknown_model > 0`.
    Four hits plus one unknown-minimum turn is an 80% hit rate, which is precisely
    where the degradation became invisible.
    """
    turns = [
        _turn(model="claude-sonnet-4-6", prefix=100, read=5000, offset_s=60 * i) for i in range(4)
    ]
    turns.append(_turn(model="claude-not-a-real-model-9", prefix=100, offset_s=300))
    diag = diagnose_cache_from_turns(turns)
    assert diag.hit_rate == 80
    assert diag.primary_failure == "miss_unknown_model"
    assert "No action needed" not in diag.remediation


def test_threshold_evidence_is_computed_from_the_offending_turns_only() -> None:
    """Review finding — the remediation number must come from turns that failed.

    Rejects: accumulating `thresholds_applied` (and the prefix average) over every
    entry before classification. Here a haiku-4-5 HIT contributes a 4096 minimum and a
    50,000-token prefix while the only failing turn is an opus-5 miss needing 512.
    A whole-window accumulator tells the user to grow the prefix to 4096 and reports an
    average computed largely from the hit.
    """
    turns = [
        _turn(model="claude-haiku-4-5", prefix=50_000, read=50_000, offset_s=0),
        _turn(model="claude-opus-5", prefix=400, offset_s=60),
    ]
    diag = diagnose_cache_from_turns(turns)
    assert diag.primary_failure == "miss_min_threshold"
    assert "512" in diag.remediation
    assert "4096" not in diag.remediation
    assert "400" in diag.evidence


def test_evidence_names_the_applied_tier_not_a_hardcoded_five_minutes() -> None:
    """Boundary rule 3, positive arm — a 1h-tier window must not be told "< 5 min".

    Rejects: HEAD's `_build_evidence`, which formats "> 5 min gap from the previous
    turn" and "keep sessions tighter (< 5 min…)" unconditionally. Here the applied
    tier IS 1h (turn 0 wrote 1h tokens) and the gap of 2 hours exceeded it, so the
    turn is a genuine `miss_ttl` whose evidence must name the tier that actually
    applied. An earlier draft asserted only that a 5m window SAYS "5 min", which is
    true of the unchanged implementation and therefore proved nothing.
    """
    one_h_exceeded = diagnose_cache_from_turns(
        [
            _turn(model="claude-sonnet-4-6", prefix=6000, w1h=5000, offset_s=0),
            _turn(model="claude-sonnet-4-6", prefix=6000, w5m=1, offset_s=7200),
        ]
    )
    assert one_h_exceeded.primary_failure == "miss_ttl"
    assert "5 min" not in one_h_exceeded.evidence
    assert "5 min" not in one_h_exceeded.remediation
    assert "1 hour" in one_h_exceeded.evidence or "1h" in one_h_exceeded.evidence


def test_evidence_states_the_minimum_is_unknown_for_an_unknown_model() -> None:
    """Boundary rule 3, absent-case arm — the degraded diagnosis must say so.

    Rejects: HEAD, where an unknown model resolves through `_DEFAULT_THRESHOLD` and
    the evidence confidently reads "prefix < 1024 tokens" — a fabricated number. Also
    rejects an `int | None` threshold formatted straight into the old f-string, which
    emits the literal "prefix >= None tokens".

    Anchored on the CONTRACT, not on wording. An earlier version asserted the literal
    word "unknown" appeared in the evidence; rewording the same sentence to "no
    published minimum ... on record" turned it red while the invariant held perfectly —
    `[fail:test] test-pins-implementation-name-not-contract`. What the SPEC actually
    requires is that the turn is surfaced as explicitly unclassified rather than
    silently measured against a guess, so the observables are: the verdict label, the
    offending id, the ABSENCE of any threshold claim, and a remediation that does not
    pretend the window is clean.
    """
    unknown = diagnose_cache_from_turns(
        [_turn(model="claude-not-a-real-model-9", prefix=100, offset_s=60 * i) for i in range(4)]
    )
    assert unknown.primary_failure == "miss_unknown_model"
    assert "claude-not-a-real-model-9" in unknown.evidence
    # No threshold is known, so NO published minimum may appear — asserted against the
    # table's own values rather than a prose pattern. A `re.search(r"prefix\s*[<>≥]")`
    # guard matched the old wording but would sleep through this file's current
    # sentence shape ("a prefix below the applicable 512-token minimum"); checking the
    # numbers is wording-independent and strictly stronger.
    for value in _MIN_CACHEABLE_PREFIX.values():
        assert str(value) not in unknown.evidence
        assert str(value) not in unknown.remediation
    assert "None" not in unknown.evidence
    assert "None" not in unknown.remediation
    # The remediation must not manufacture an errand. An earlier revision said "report
    # the id above so it can be added" — while this module deliberately REFUSES to add
    # rows it cannot cite, so every user of a currently-shipping model in that set was
    # handed a task the code will not complete.
    assert "report the id" not in unknown.remediation.lower()
    assert "upgrade" not in unknown.remediation.lower()
    assert "No action is available on your side" in unknown.remediation
