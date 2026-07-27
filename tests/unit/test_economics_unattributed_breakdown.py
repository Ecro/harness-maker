"""PLAN Phase 2 — the `(unattributed)` bucket is decomposed on an observable predicate.

Every test here names the wrong implementation it rejects. The bucket-conservation
half is trivially satisfiable (see AC-010's note: `recoverable = est is not None`
passes all four conservation/presence conjuncts while implementing none of ADR-013),
so the positive arm is what carries the weight.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from harness_maker.economics import (
    UNATTRIBUTED,
    EconomicsReport,
    TokenUsage,
    TurnRecord,
    aggregate,
)
from harness_maker.stage_spans import SpanAttribution

_T0 = datetime(2026, 7, 27, 9, 0, 0, tzinfo=UTC)


def _turn(idx: int, **kw: object) -> TurnRecord:
    base: dict[str, object] = {
        "session_id": "s1",
        "ts": _T0 + timedelta(minutes=idx),
        "model": "claude-opus-5",
        "usage": TokenUsage(output_tokens=100),
        "task_slug": "demo",
        "cwd": "/repo/proj",
        "git_branch": "hm/demo",
    }
    base.update(kw)
    return TurnRecord(**base)  # type: ignore[arg-type]


def _mixed_window() -> list[TurnRecord]:
    """One turn per ADR-013 arm, with distinct USD so a swapped bucket is visible.

    - idx 0: attributed anchor (`direct`) — outside the decomposed population.
    - idx 1: adjacency-resolvable from that anchor → `recoverable`.
    - idx 2: a DIFFERENT session, so adjacency cannot reach it, but
      `preceded_by_user` — the union arm the broken implementation drops.
    - idx 3: same session as idx 2, neither resolvable nor user-adjacent →
      `unrecoverable_in_window`.
    """
    return [
        _turn(0, attribution_skill="hm:execute"),
        _turn(1, usage=TokenUsage(output_tokens=100)),
        _turn(2, session_id="s2", usage=TokenUsage(output_tokens=200), preceded_by_user=True),
        _turn(3, session_id="s2", usage=TokenUsage(output_tokens=400)),
    ]


# ------------------------------------------------------------------ AC-010


def test_unattributed_decomposes_and_sums() -> None:
    """AC-010's executable predicate, bound to the real aggregate over a real window.

    Evaluated through `model_dump(mode="json")` — the shipped `economics report`
    surface — so a field that exists in memory but never serialises fails here.
    """
    report = aggregate(_mixed_window()).model_dump(mode="json")

    assert set(report["unattributed_breakdown"]) >= {"recoverable", "unrecoverable_in_window"}
    assert all(v["turns"] > 0 for v in report["unattributed_breakdown"].values())
    assert (
        sum(v["turns"] for v in report["unattributed_breakdown"].values())
        == report["by_stage"][UNATTRIBUTED]["turns"]
    )
    # RELATIVE tolerance, not absolute: the two sides are differently-ordered float
    # accumulations, and an absolute 1e-9 is vacuous at this fixture's $0.0175 while
    # being smaller than the worst-case divergence on the live ~$8,960 window.
    assert abs(
        sum(v["usd"] for v in report["unattributed_breakdown"].values())
        - report["by_stage"][UNATTRIBUTED]["total_usd"]
    ) <= 1e-9 * abs(report["by_stage"][UNATTRIBUTED]["total_usd"])
    assert (
        report["unattributed_breakdown"]["recoverable"]["turns"]
        > report["turns_by_attribution_source"]["adjacency"]
    )


# ------------------------------------------------------------------ named rejections


def test_recoverable_counts_user_adjacent_turns_not_only_adjacency_resolvable() -> None:
    """Rejects `recoverable = {turns where est is not None}` (AC-010's named break).

    That implementation reproduces `turns_by_attribution_source["adjacency"]` exactly.
    The window has one adjacency-resolvable turn and one user-adjacent turn in a
    session adjacency cannot reach, so the union must be strictly larger by one.

    The exact per-bucket USD also rejects a WRONG-MEMBERSHIP implementation that gets
    the counts right — e.g. reading `preceded_by_user` off `turns[idx - 1]`, which
    yields {idx1, idx3} and {idx2}: still 2 and 1, so the counts alone cannot see it.
    The three unattributed turns cost 0.0025 / 0.005 / 0.01 (`claude-opus-5` output
    at 25.0/1e6 over 100 / 200 / 400 output tokens), so the correct partition is the
    only one summing to these two values.
    """
    report = aggregate(_mixed_window())
    breakdown = report.unattributed_breakdown

    adjacency = report.turns_by_attribution_source["adjacency"]
    assert adjacency == 1
    assert breakdown["recoverable"].turns == adjacency + 1
    assert breakdown["recoverable"].usd == pytest.approx(0.0025 + 0.005)
    assert breakdown["unrecoverable_in_window"].usd == pytest.approx(0.01)


def test_both_buckets_carry_real_usd_so_an_all_zeros_breakdown_fails() -> None:
    """Rejects a hardcoded all-zeros breakdown, and a turns-only one.

    A `{"recoverable": {"turns": 0, "usd": 0.0}, ...}` stub satisfies neither the
    strict positivity below nor the USD identity, and an implementation that counts
    turns but forgets to accumulate cost fails the second half alone.
    """
    report = aggregate(_mixed_window())
    breakdown = report.unattributed_breakdown

    assert breakdown["recoverable"].turns == 2
    assert breakdown["unrecoverable_in_window"].turns == 1
    assert breakdown["recoverable"].usd > 0.0
    assert breakdown["unrecoverable_in_window"].usd > 0.0
    assert abs(
        breakdown["recoverable"].usd
        + breakdown["unrecoverable_in_window"].usd
        - report.by_stage[UNATTRIBUTED].total_usd
    ) <= 1e-9 * abs(report.by_stage[UNATTRIBUTED].total_usd)


def test_a_capped_turn_is_never_recoverable_even_when_user_adjacent() -> None:
    """ADR-013: the span cap is TERMINAL, so user-adjacency does not re-open it.

    The cap already forces `est = None`, so an implementation that only checks
    adjacency inherits this for free. It does NOT inherit it for the
    `preceded_by_user` arm — that arm has to be gated explicitly, and this test is
    the only thing that says so.
    """
    turns = [
        _turn(0, attribution_skill="hm:execute"),
        _turn(1, preceded_by_user=True),
    ]
    spans = SpanAttribution(stages=(None, None), capped_indices=(1,))
    report = aggregate(turns, spans=spans)

    assert report.capped_turns == 1
    assert report.unattributed_breakdown["recoverable"].turns == 0
    assert report.unattributed_breakdown["unrecoverable_in_window"].turns == 1


def test_an_empty_unattributed_population_emits_no_buckets_and_no_notes() -> None:
    """A decomposition OF a bucket must not exist when the bucket does not.

    Rejects unconditionally seeding both keys: that reports a partition of nothing,
    and it is the shape that lets an all-zeros breakdown look structurally healthy.
    """
    report = aggregate([_turn(0, attribution_skill="hm:execute")])

    assert UNATTRIBUTED not in report.by_stage
    assert report.unattributed_breakdown == {}
    assert report.unattributed_breakdown_notes == []


def test_notes_state_the_meaning_of_recoverable_and_the_population_absences() -> None:
    """ADR-013 requires the re-framing to be observable in the artifact, not prose.

    Rejects shipping the buckets without the notes, and rejects notes that describe
    Cursor/Codex or flag-off harnesses as a THIRD bucket rather than as absences.
    """
    report = aggregate(_mixed_window()).model_dump(mode="json")
    notes = report["unattributed_breakdown_notes"]

    assert notes, "the breakdown shipped without its own field documentation"
    joined = " ".join(notes).lower()
    # ADR-013's ⚠️ consequence, in the ADR's own words: "'recoverable' means
    # *adjacency-resolvable*, not *will be recovered*". Asserting on those two phrases
    # rather than on fragments — `recover` is a substring of both bucket keys and `not`
    # is a substring of `note`, so a fragment test passes on notes that say neither.
    assert "adjacency-resolvable" in joined
    assert "will be recovered" in joined
    assert "cursor" in joined
    assert "codex" in joined
    assert "feature_branch_workflow" in joined
    # The absences must not have become buckets.
    assert set(report["unattributed_breakdown"]) == {"recoverable", "unrecoverable_in_window"}
    # Note 1 points the reader at a SIBLING FIELD by name. Nothing else ties that
    # string to the field, so a rename would leave a shipped user-facing note aimed
    # at something that no longer exists. This is the gate.
    assert "classification_cache_misses" in joined
    assert "classification_cache_misses" in EconomicsReport.model_fields
