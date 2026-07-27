"""AC-003 — the price table states the published rates and declares its version.

The 30-day measurement this plan is built on priced every `claude-opus-5` turn at
$15/$75 because `resolve_model_family` matches `"opus"` as a substring. These
assertions pin published values, not relations — the `[fail:test]
assertion-invariant-over-named-dimension` prevention rule.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from harness_maker.cache_diagnostics import _threshold_for_model, diagnose_cache_from_turns
from harness_maker.economics import (
    PRICE_TABLE,
    PRICE_TABLE_EFFECTIVE_DATE,
    PRICE_TABLE_VERSION,
    ModelPrice,
    TokenUsage,
    TurnRecord,
    aggregate,
    price_turn,
    resolve_model_family,
)

# The pre-change values, pinned here so the "changed" arms cannot silently become
# no-ops if someone edits the constants without touching this file.
_PRE_CHANGE_PRICE_TABLE_VERSION = "1"
_PRE_CHANGE_PRICE_TABLE_EFFECTIVE_DATE = "2026-07-25"


def _turn_for(model: str) -> TurnRecord:
    return TurnRecord(
        session_id="s1",
        ts=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        model=model,
        usage=TokenUsage(input_tokens=1000, output_tokens=100),
    )


def _price_for(model: str) -> ModelPrice:
    family = resolve_model_family(model)
    assert family is not None, f"{model} resolves to no price-table key"
    return PRICE_TABLE[family]


def test_opus5_rate_and_versioned_history() -> None:
    """Opus 5 at the published 5/25 with documented cache multipliers.

    Rejects: the shipped table, where `"opus"` captures `claude-opus-5` at 15/75.
    Each multiplier is pinned to its computed value (0.1x read, 1.25x 5m write,
    2.0x 1h write of the 5.0 input rate) rather than to a ratio — a ratio holds
    for the wrong base rate too.
    """
    opus5 = _price_for("claude-opus-5")
    assert opus5.input == 5.0
    assert opus5.output == 25.0
    assert opus5.cache_read == 0.5
    assert opus5.cache_write_5m == 6.25
    assert opus5.cache_write_1h == 10.0

    # ADR-002: haiku was 0.25/1.25 against a published 1/5.
    haiku = _price_for("claude-haiku-4-5")
    assert haiku.input == 1.0
    assert haiku.output == 5.0

    # ADR-002 L1: `opus` stays at the pre-4.5 rate, so 4.5 needs its own key or it
    # sits on the wrong side of this ADR's own boundary.
    assert _price_for("claude-opus-4-5").input == 5.0

    # ADR-003: both provenance signals move, not just the version label. Pinned to
    # VALUES, not `!=` relations — `PRICE_TABLE_VERSION = "banana"` satisfied a `!=`
    # arm, and a one-shot `!=` can never fire again after the first bump. Pinning means
    # the next rate edit must touch this file and cannot ship with a stale label.
    assert PRICE_TABLE_VERSION == "2"
    assert PRICE_TABLE_EFFECTIVE_DATE == "2026-07-27"
    assert PRICE_TABLE_VERSION != _PRE_CHANGE_PRICE_TABLE_VERSION
    assert PRICE_TABLE_EFFECTIVE_DATE != _PRE_CHANGE_PRICE_TABLE_EFFECTIVE_DATE
    date.fromisoformat(PRICE_TABLE_EFFECTIVE_DATE)  # raises if not a real ISO date


def test_pre_4_5_haiku_still_prices_at_the_legacy_rate() -> None:
    """The counterpart the opus row has had all along.

    Rejects: editing the `haiku` family row to Haiku 4.5's 1/5 instead of adding a
    `haiku-4-5` key. The 0.25/1.25 that row carries is the published Haiku 3 rate, so
    overwriting it reprices every older Haiku turn 4x — the same class of error this
    table exists to remove, in the opposite direction. Note that asserting
    `price_for("claude-haiku-4-5").input == 1.0` does NOT catch this: in the broken
    world that id resolves to the overwritten family row and still reads 1.0.
    """
    assert PRICE_TABLE["haiku"].input == 0.25
    assert PRICE_TABLE["haiku"].output == 1.25
    assert resolve_model_family("claude-haiku-4-5") == "haiku-4-5"
    assert resolve_model_family("claude-haiku-3") == "haiku"


def test_per_model_keys_win_over_the_family_key() -> None:
    """Longest-match must select the point release, not the family.

    Rejects: adding per-model keys while leaving a first-match resolver, which
    returns whichever key iteration order reaches first. `claude-opus-4-7` and
    `claude-opus-5` share the `opus` prefix and must NOT resolve to it.
    """
    assert resolve_model_family("claude-opus-5") == "opus-5"
    assert resolve_model_family("claude-opus-4-7") == "opus-4-7"
    assert resolve_model_family("claude-sonnet-5") == "sonnet-5"


def test_unmatched_point_release_falls_back_to_the_family_key() -> None:
    """SPEC AC-003 clause 4 — an unlisted point release resolves, it does not error.

    Rejects: replacing the family keys with a strictly per-model table, which makes
    `resolve_model_family` return None for any release not enumerated and sends the
    turn down `price_turn`'s fallback path instead of pricing it. Asserting the
    `opus` ROW's values (as the sibling test does) does not cover this — that is a
    table lookup, this is the resolution.
    """
    assert resolve_model_family("claude-opus-4-1") == "opus"


def test_a_priced_model_with_no_published_minimum_refuses_to_guess() -> None:
    """The two tables are ALLOWED to disagree — but only in the safe direction.

    An intermediate revision asserted `priced_point_releases <= thresholded` and, to
    satisfy it, added `opus-4-5`/`sonnet-4-5` to `_MIN_CACHEABLE_PREFIX` at an inherited
    1024 that no release-specific source publishes. That gate conflated "we price this
    model" with "its cache minimum is documented", and so it *required* inventing the
    number that returning `None` exists to refuse. It is replaced by its inverse.

    Rejects: adding a bare-family row (`opus`, `sonnet`, `haiku`) to
    `_MIN_CACHEABLE_PREFIX`, or re-adding `opus-4-5`/`sonnet-4-5` at an inherited value.
    `claude-opus-4-5` prices fine (5.0) and must still produce no threshold verdict — a
    wrong rate costs an approximate dollar figure, a wrong minimum costs a confident
    diagnosis and a remediation the user cannot act on.

    Scope is stated narrowly on purpose. This does NOT reject every fallback minimum:
    keys are matched as substrings, so a hypothetical `claude-opus-5-1` contains
    `opus-5` and would inherit 512. These two ids happen not to contain any key, which
    is why they resolve to None — the module comment records that limitation and why
    tightening only this matcher is rejected (ADR-002 locks the shared contract).
    """
    assert _price_for("claude-opus-4-5").input == 5.0
    assert _threshold_for_model("claude-opus-4-5") is None
    assert _threshold_for_model("claude-sonnet-4-5") is None

    diag = diagnose_cache_from_turns(
        [
            TurnRecord(
                session_id="s1",
                ts=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
                model="claude-opus-4-5",
                usage=TokenUsage(input_tokens=100, output_tokens=1),
            )
        ]
    )
    assert diag.counters["miss_min_threshold"] == 0


def test_a_family_priced_turn_is_visible_in_the_report() -> None:
    """R8 — the recurrence path of the defect this whole change exists to fix.

    `resolve_model_family` matches SUBSTRINGS, so a model released after this table is
    written matches its FAMILY key: `claude-opus-9` resolves to `"opus"`, which is
    non-None, so `price_turn`'s `used_fallback = family is None` stays False and the
    turn is priced at the pre-4.5 15/75 while appearing in NEITHER `unknown_models` NOR
    `fallback_priced_turns`. That is exactly how `"opus"` captured `claude-opus-5` and
    overstated 30 days of spend 3x — and it is guaranteed to happen again at the next
    model release, silently, unless something records it.

    This adds observability, not a policy change: the family row keeps serving as the
    fallback and no rate moves. Four arms, each rejecting a named implementation:

    1. `claude-opus-9` flagged — rejects the shipped state, where no signal exists.
    2. `claude-opus-5` NOT flagged — rejects "flag every turn".
    3. `gpt-4` sets `priced_with_fallback` but NOT `priced_with_family_row` — rejects
       collapsing two distinct signals into one.
    4. the aggregate exposes it — rejects "computed but never surfaced", the
       `config-set-in-memory-must-serialize-to-the-consumed-file` shape this repo has
       shipped before. Arms 1-3 alone would all pass against a flag no report reads.
    """
    future = _turn_for("claude-opus-9")
    enumerated = _turn_for("claude-opus-5")
    unpriceable = _turn_for("gpt-4")

    assert price_turn(future).priced_with_family_row is True
    assert price_turn(future).priced_with_fallback is False
    assert price_turn(enumerated).priced_with_family_row is False
    assert price_turn(unpriceable).priced_with_fallback is True
    assert price_turn(unpriceable).priced_with_family_row is False

    report = aggregate([future, enumerated, unpriceable])
    assert report.family_priced_turns == 1
    assert report.family_priced_models == {"claude-opus-9": 1}
    assert report.fallback_priced_turns == 1

    # Through the SERIALISED form the CLI actually emits (`model_dump(mode="json")` at
    # the `economics report` entry point), not just the in-memory attribute. A field
    # that aggregates correctly but never reaches the payload is the
    # `config-set-in-memory-must-serialize-to-the-consumed-file` shape, and the whole
    # point of this signal is that a human reads it.
    payload = report.model_dump(mode="json")
    assert payload["family_priced_turns"] == 1
    assert payload["family_priced_models"] == {"claude-opus-9": 1}


def test_pre_4_5_opus_still_prices_at_the_legacy_rate() -> None:
    """The `opus` fallback is deliberately retained (ADR-002).

    Rejects: editing the single `opus` row to 5/25, which would leave genuine
    pre-4.5 Opus turns priced 3x under.
    """
    assert PRICE_TABLE["opus"].input == 15.0
    assert PRICE_TABLE["opus"].output == 75.0
