"""Phase 1 pure-layer contract: ordered-ladder classification, pricing, aggregation."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel

from harness_maker.economics import (
    PRICE_TABLE_EFFECTIVE_DATE,
    PRICE_TABLE_VERSION,
    AdjacencyBounds,
    EconomicsReport,
    TokenUsage,
    TurnRecord,
    aggregate,
    classify_turns,
    estimate_attribution,
    price_turn,
    ratio_field_kinds,
)

_T0 = datetime(2026, 7, 25, 12, 0, 0, tzinfo=UTC)


def _turn(
    idx: int = 0,
    *,
    skill: str | None = None,
    agent: str | None = None,
    paths: tuple[str, ...] = (),
    task: str | None = "demo",
    model: str = "claude-opus-5",
    usage: TokenUsage | None = None,
    session: str = "s1",
    minutes: float | None = None,
    sidechain: bool = False,
    cwd: str | None = "/repo",
    branch: str | None = "hm/demo",
) -> TurnRecord:
    return TurnRecord(
        session_id=session,
        ts=_T0 + timedelta(minutes=minutes if minutes is not None else idx),
        model=model,
        usage=usage or TokenUsage(output_tokens=100),
        attribution_skill=skill,
        attribution_agent=agent,
        is_sidechain=sidechain,
        task_slug=task,
        written_paths=paths,
        cwd=cwd,
        git_branch=branch,
    )


# ---------------------------------------------------------------- ladder


def test_every_turn_gets_exactly_one_label_and_the_sequence_is_pinned() -> None:
    turns = [
        _turn(0, paths=("a.py",)),
        _turn(1, skill="hm:review"),
        _turn(2),
        _turn(3, paths=("a.py",)),
        _turn(4, agent="code-reviewer", sidechain=True),
    ]
    # turn 3 is PRODUCE (not REWORK): the VERIFY at index 1 cleared a.py's rewrite window.
    assert classify_turns(turns) == ["PRODUCE", "VERIFY", "OTHER", "PRODUCE", "VERIFY"]


def test_first_write_is_produce_not_rework() -> None:
    assert classify_turns([_turn(0, paths=("a.py",))]) == ["PRODUCE"]


def test_unprompted_rewrite_is_rework() -> None:
    labels = classify_turns([_turn(0, paths=("a.py",)), _turn(1, paths=("a.py",))])
    assert labels == ["PRODUCE", "REWORK"]


def test_review_driven_rewrite_is_produce_not_rework() -> None:
    """ADR-003 rule 1 VERIFY-clause — the Interview #1 principle, encoded."""
    labels = classify_turns(
        [
            _turn(0, paths=("a.py",)),
            _turn(1, skill="hm:review"),
            _turn(2, paths=("a.py",)),
        ]
    )
    assert labels == ["PRODUCE", "VERIFY", "PRODUCE"]


def test_writing_turn_carrying_review_skill_is_produce() -> None:
    """ADR-003 rule 2's writes-nothing clause. Authority: Phase 1 exit criterion."""
    labels = classify_turns(
        [_turn(0, paths=("a.py",)), _turn(1, skill="hm:review", paths=("a.py",))]
    )
    assert labels == ["PRODUCE", "PRODUCE"]


def test_writing_turn_carrying_reviewer_agent_is_produce() -> None:
    labels = classify_turns([_turn(0, agent="code-reviewer", paths=("a.py",), sidechain=True)])
    assert labels == ["PRODUCE"]


def test_reviewer_agent_turn_is_verify() -> None:
    assert classify_turns([_turn(0, agent="security-reviewer", sidechain=True)]) == ["VERIFY"]


def test_non_writing_non_review_turn_is_other() -> None:
    assert classify_turns([_turn(0)]) == ["OTHER"]


def test_multi_path_turn_is_rework_only_when_every_path_is_a_rewrite() -> None:
    labels = classify_turns(
        [
            _turn(0, paths=("a.py",)),
            _turn(1, paths=("a.py", "b.py")),  # b.py is new -> PRODUCE
            _turn(2, paths=("a.py", "b.py")),  # both seen -> REWORK
        ]
    )
    assert labels == ["PRODUCE", "PRODUCE", "REWORK"]


def test_rework_requires_same_task() -> None:
    labels = classify_turns(
        [_turn(0, paths=("a.py",), task="one"), _turn(1, paths=("a.py",), task="two")]
    )
    assert labels == ["PRODUCE", "PRODUCE"]


def test_turn_without_task_slug_is_never_rework() -> None:
    labels = classify_turns(
        [_turn(0, paths=("a.py",), task=None), _turn(1, paths=("a.py",), task=None)]
    )
    assert labels == ["PRODUCE", "PRODUCE"]


def test_verify_only_clears_rework_for_its_own_task() -> None:
    labels = classify_turns(
        [
            _turn(0, paths=("a.py",), task="one"),
            _turn(1, skill="hm:review", task="two"),
            _turn(2, paths=("a.py",), task="one"),
        ]
    )
    assert labels[2] == "REWORK"


# ---------------------------------------------------------------- pricing


def test_pricing_is_linear() -> None:
    single = price_turn(_turn(usage=TokenUsage(output_tokens=1000)))
    double = price_turn(_turn(usage=TokenUsage(output_tokens=2000)))
    assert single.total_usd > 0
    assert double.total_usd == pytest.approx(2 * single.total_usd)


def test_token_types_are_priced_independently() -> None:
    out = price_turn(_turn(usage=TokenUsage(output_tokens=1_000_000))).total_usd
    read = price_turn(_turn(usage=TokenUsage(cache_read_tokens=1_000_000))).total_usd
    inp = price_turn(_turn(usage=TokenUsage(input_tokens=1_000_000))).total_usd
    assert out > inp > read > 0
    combined = price_turn(
        _turn(
            usage=TokenUsage(
                output_tokens=1_000_000, cache_read_tokens=1_000_000, input_tokens=1_000_000
            )
        )
    ).total_usd
    assert combined == pytest.approx(out + read + inp)


def test_cache_write_tiers_are_priced_separately() -> None:
    five_m = price_turn(_turn(usage=TokenUsage(cache_write_5m_tokens=1_000_000))).total_usd
    one_h = price_turn(_turn(usage=TokenUsage(cache_write_1h_tokens=1_000_000))).total_usd
    assert one_h > five_m > 0


def test_mixed_model_window_prices_each_turn_at_its_own_rate() -> None:
    """ADR-010 — a single-rate window (the rejected alternative) fails this."""
    usage = TokenUsage(output_tokens=1_000_000)
    opus = _turn(0, model="claude-opus-5", usage=usage)
    haiku = _turn(1, model="claude-haiku-4-5-20251001", usage=usage)
    assert price_turn(opus).total_usd > price_turn(haiku).total_usd

    rep = aggregate([opus, haiku])
    assert rep.total_usd == pytest.approx(price_turn(opus).total_usd + price_turn(haiku).total_usd)
    # A window priced entirely at one model's rate would double either side.
    assert rep.total_usd != pytest.approx(2 * price_turn(opus).total_usd)
    assert rep.total_usd != pytest.approx(2 * price_turn(haiku).total_usd)


def test_unknown_model_uses_fallback_and_is_flagged() -> None:
    cost = price_turn(_turn(model="gpt-nonexistent"), fallback_model="opus")
    assert cost.priced_with_fallback is True
    assert cost.total_usd > 0
    assert price_turn(_turn(model="claude-opus-5")).priced_with_fallback is False


def test_report_carries_the_price_table_version_and_effective_date() -> None:
    """ADR-010 reproducibility: the constant's CONSUMER is what must be pinned."""
    rep = aggregate([_turn(0)])
    assert rep.price_table_version == PRICE_TABLE_VERSION
    assert rep.price_table_effective_date == PRICE_TABLE_EFFECTIVE_DATE
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", rep.price_table_effective_date)


def test_unknown_models_are_reported_separately() -> None:
    rep = aggregate([_turn(0, model="gpt-nonexistent"), _turn(1, model="claude-opus-5")])
    assert rep.unknown_models == {"gpt-nonexistent": 1}
    assert rep.fallback_priced_turns == 1


# ---------------------------------------------------------------- aggregate


def test_aggregate_conserves_cost_across_categories() -> None:
    turns = [
        _turn(0, paths=("a.py",), skill="hm:execute"),
        _turn(1, skill="hm:review"),
        _turn(2, paths=("a.py",), skill="hm:execute"),
        _turn(3),
    ]
    rep = aggregate(turns)
    total_of_turns = sum(price_turn(t).total_usd for t in turns)
    assert rep.total_usd > 0
    assert rep.total_usd == pytest.approx(total_of_turns)
    assert sum(c.total_usd for c in rep.by_category.values()) == pytest.approx(total_of_turns)
    assert sum(s.total_usd for s in rep.by_stage.values()) == pytest.approx(total_of_turns)


def test_carry_ratio_is_pinned_for_an_all_cache_read_window() -> None:
    turns = [_turn(0, usage=TokenUsage(cache_read_tokens=1_000_000, output_tokens=1))]
    rep = aggregate(turns)
    cost = price_turn(turns[0])
    assert rep.carry_ratio == pytest.approx(cost.cache_read_usd / cost.total_usd)
    assert rep.carry_ratio > 0.99


def test_carry_ratio_is_zero_for_an_output_only_window() -> None:
    rep = aggregate([_turn(0, usage=TokenUsage(output_tokens=1_000))])
    assert rep.carry_ratio == pytest.approx(0.0)


def test_aggregate_reports_mean_context_per_turn() -> None:
    turns = [
        _turn(0, usage=TokenUsage(cache_read_tokens=100, input_tokens=10)),
        _turn(1, usage=TokenUsage(cache_read_tokens=300, input_tokens=10)),
    ]
    rep = aggregate(turns)
    assert rep.by_stage["(unattributed)"].mean_context_tokens == pytest.approx(210.0)


def test_unattributed_bucket_is_reported_with_its_true_total() -> None:
    turns = [_turn(0, skill="hm:execute"), _turn(1), _turn(2)]
    rep = aggregate(turns)
    honest = rep.by_stage["(unattributed)"].total_usd
    assert honest == pytest.approx(sum(price_turn(t).total_usd for t in turns[1:]))


def test_adjacency_estimate_never_mutates_the_honest_bucket() -> None:
    """ADR-006 invariant."""
    turns = [_turn(0, skill="hm:execute"), _turn(1, minutes=1), _turn(2, minutes=2)]
    without = aggregate(turns, bounds=AdjacencyBounds(enabled=False))
    with_est = aggregate(turns, bounds=AdjacencyBounds(enabled=True))
    assert with_est.by_stage["(unattributed)"].total_usd == pytest.approx(
        without.by_stage["(unattributed)"].total_usd
    )
    assert with_est.estimated_attribution_usd.get("hm:execute", 0.0) > 0.0
    assert without.estimated_attribution_usd == {}


def test_estimator_coverage_is_one_when_all_unattributed_spend_is_claimable() -> None:
    turns = [_turn(0, skill="hm:execute"), _turn(1, minutes=1)]
    rep = aggregate(turns, bounds=AdjacencyBounds(enabled=True))
    assert rep.estimator_coverage == pytest.approx(1.0)


def test_estimator_coverage_is_partial_when_some_spend_is_out_of_bounds() -> None:
    turns = [
        _turn(0, skill="hm:execute", minutes=0),
        _turn(1, minutes=1),  # in bounds
        _turn(2, minutes=100),  # beyond max_gap_min
    ]
    rep = aggregate(turns, bounds=AdjacencyBounds(max_gap_min=10))
    assert rep.estimator_coverage == pytest.approx(0.5)


def test_estimator_coverage_is_zero_when_estimation_is_disabled() -> None:
    turns = [_turn(0, skill="hm:execute"), _turn(1, minutes=1)]
    rep = aggregate(turns, bounds=AdjacencyBounds(enabled=False))
    assert rep.estimator_coverage == pytest.approx(0.0)


def test_wall_clock_is_reported_per_scope() -> None:
    turns = [
        _turn(0, skill="hm:review", minutes=0),
        _turn(1, skill="hm:review", minutes=1),
        _turn(2, skill="hm:review", minutes=0.5, agent="code-reviewer", sidechain=True),
        _turn(3, skill="hm:review", minutes=1.5, agent="code-reviewer", sidechain=True),
    ]
    rep = aggregate(turns)
    assert rep.wall_clock_seconds_by_scope["main"] == pytest.approx(60.0)
    assert rep.wall_clock_seconds_by_scope["subagent"] == pytest.approx(60.0)


def test_no_cross_scope_wall_clock_total_field_exists() -> None:
    """Scopes overlap in real time; a summed total would be misleading (ADR text)."""
    names = set(EconomicsReport.model_fields)
    assert not {n for n in names if "wall_clock" in n and "by_scope" not in n}


def test_idle_gaps_are_capped_at_the_configured_value() -> None:
    near = aggregate([_turn(0, minutes=0), _turn(1, minutes=1)], idle_gap_cap_min=5)
    far = aggregate([_turn(0, minutes=0), _turn(1, minutes=600)], idle_gap_cap_min=5)
    assert near.wall_clock_seconds_by_scope["main"] == pytest.approx(60.0)
    assert far.wall_clock_seconds_by_scope["main"] == pytest.approx(300.0)


def test_idle_gap_cap_is_configurable() -> None:
    far = aggregate([_turn(0, minutes=0), _turn(1, minutes=600)], idle_gap_cap_min=2)
    assert far.wall_clock_seconds_by_scope["main"] == pytest.approx(120.0)


def test_rework_coverage_distinguishes_unmeasurable_from_zero() -> None:
    measurable = aggregate([_turn(0, paths=("a.py",), task="demo")])
    unmeasurable = aggregate([_turn(0, paths=("a.py",), task=None, branch=None)])
    assert measurable.rework_coverage == pytest.approx(1.0)
    assert unmeasurable.rework_coverage == pytest.approx(0.0)


def test_empty_input_produces_an_empty_but_valid_report() -> None:
    rep = aggregate([])
    assert rep.total_usd == 0.0
    assert rep.by_stage == {}
    assert rep.carry_ratio == 0.0
    assert rep.estimator_coverage == 0.0


# ---------------------------------------------------------------- adjacency bounds


@pytest.mark.parametrize(
    ("minutes", "expect_attributed"),
    [
        (5.0, True),  # comfortably inside
        (10.0, True),  # AT the bound — ADR-006 says "<= max_gap_min"
        (10.5, False),  # first rejecting value
        (30.0, False),  # comfortably outside
    ],
)
def test_adjacency_gap_bound(minutes: float, expect_attributed: bool) -> None:
    turns = [_turn(0, skill="hm:execute", minutes=0), _turn(1, minutes=minutes)]
    est = estimate_attribution(turns, AdjacencyBounds(max_gap_min=10))
    assert (est[1] is not None) is expect_attributed


def test_adjacency_turn_distance_bound_rejects_at_the_boundary() -> None:
    turns = [_turn(0, skill="hm:execute", minutes=0)]
    turns += [_turn(i, minutes=i * 0.1) for i in range(1, 6)]
    est = estimate_attribution(turns, AdjacencyBounds(max_turns=3, max_gap_min=1000))
    assert est[3] is not None  # AT the bound — accepted
    assert est[4] is None  # first rejecting distance
    assert est[5] is None


def test_adjacency_stops_at_session_boundary() -> None:
    turns = [
        _turn(0, skill="hm:execute", session="s1", minutes=0),
        _turn(1, session="s2", minutes=0.5),
    ]
    assert estimate_attribution(turns, AdjacencyBounds())[1] is None


def test_adjacency_stops_at_task_change() -> None:
    turns = [
        _turn(0, skill="hm:execute", task="one", minutes=0),
        _turn(1, task="two", minutes=0.5),
    ]
    assert estimate_attribution(turns, AdjacencyBounds())[1] is None


def test_adjacency_stops_at_branch_change_even_without_a_task_slug() -> None:
    turns = [
        _turn(0, skill="hm:execute", task=None, branch="feature/a", minutes=0),
        _turn(1, task=None, branch="feature/b", minutes=0.5),
    ]
    assert estimate_attribution(turns, AdjacencyBounds())[1] is None


def test_adjacency_stops_at_cwd_change() -> None:
    turns = [
        _turn(0, skill="hm:execute", cwd="/a", minutes=0),
        _turn(1, cwd="/b", minutes=0.5),
    ]
    assert estimate_attribution(turns, AdjacencyBounds())[1] is None


def test_adjacency_disabled_attributes_nothing() -> None:
    turns = [_turn(0, skill="hm:execute", minutes=0), _turn(1, minutes=0.5)]
    assert estimate_attribution(turns, AdjacencyBounds(enabled=False)) == [None, None]


# ---------------------------------------------------------------- ADR-002 machine invariant

_COST_PER_COUNT_NAME = re.compile(r"(^|_)(per)(_|$)|cost_per|usd_per")


def _all_model_field_names(model: type[BaseModel], seen: set[type] | None = None) -> set[str]:
    """Fields AND computed properties — a @property would otherwise evade the invariant."""
    seen = seen if seen is not None else set()
    if model in seen:
        return set()
    seen.add(model)
    names: set[str] = {
        n
        for n in vars(model)
        if isinstance(getattr(model, n, None), property) and not n.startswith("_")
    }
    for name, field in model.model_fields.items():
        names.add(name)
        for arg in (field.annotation, *getattr(field.annotation, "__args__", ())):
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                names |= _all_model_field_names(arg, seen)
    return names


def test_no_report_field_divides_cost_by_a_count() -> None:
    """ADR-002 data-layer enforcement. The prose layer is instruction, not enforcement.

    Binds the REAL schema, not just the implementation's own declaration — otherwise
    adding `cost_per_landed_commit` and omitting it from the declaration would pass.
    """
    schema_names = _all_model_field_names(EconomicsReport)
    offenders = sorted(n for n in schema_names if _COST_PER_COUNT_NAME.search(n))
    assert offenders == [], f"cost-per-deliverable-shaped field(s) in the schema: {offenders}"

    kinds = ratio_field_kinds()
    assert kinds, "the report must declare its ratio fields for this invariant to mean anything"
    declared_offenders = {
        name: (num, den) for name, (num, den) in kinds.items() if num == "cost" and den == "count"
    }
    assert declared_offenders == {}
    assert set(kinds) <= schema_names


def test_declared_ratio_fields_cover_every_ratio_shaped_field() -> None:
    declared = set(ratio_field_kinds())
    shaped = {
        name
        for name in _all_model_field_names(EconomicsReport)
        if name.endswith(("_ratio", "_coverage", "_rate"))
    }
    assert shaped <= declared, f"undeclared ratio-shaped field(s): {shaped - declared}"
