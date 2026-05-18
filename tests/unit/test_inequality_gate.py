"""Unit tests for inequality_gate.apply_inequality_gate (PLAN F4)."""

from __future__ import annotations

from typing import Any

import pytest

from harness_maker.common_ground import CGMark
from harness_maker.eig import ScoringContext, clear_eig_cache
from harness_maker.inequality_gate import (
    Candidate,
    GateConfig,
    apply_inequality_gate,
)


@pytest.fixture(autouse=True)
def _reset_eig_cache() -> None:
    """EIG cache is process-lifetime; isolate tests."""
    clear_eig_cache()


def _high_eig(q: str, ctx: ScoringContext) -> float:
    return 0.8


def _low_eig(q: str, ctx: ScoringContext) -> float:
    return 0.3


def _q_specific_eig(scores: dict[str, float]) -> Any:
    """Return a mechanism that maps question text → predetermined EIG."""

    def fn(q: str, ctx: ScoringContext) -> float:
        return scores.get(q, 0.0)

    return fn


def _cfg(**kwargs: Any) -> GateConfig:
    return GateConfig(**kwargs)


# ---------- 5-term filter table ---------------------------------------------------------


def test_all_five_terms_pass_marks_overall_pass() -> None:
    """A candidate clearing every term has overall_pass=True."""
    c = Candidate(slot="Some slot", question="What is X?")
    results = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)
    assert len(results) == 1
    r = results[0]
    assert r.overall_pass is True
    assert r.passed_count == 5


def test_eig_below_epsilon_blocks() -> None:
    """EIG < ε fails the EIG term and overall."""
    c = Candidate(slot="X", question="Q?")
    results = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_low_eig)
    assert results[0].eig_pass is False
    assert results[0].overall_pass is False


def test_clariti_below_threshold_blocks() -> None:
    """TaskRel * UserAns < 0.7 fails CLARITI."""
    c = Candidate(slot="X", question="Q?", task_relevance=0.5, user_answerability=0.5)
    results = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)
    assert results[0].clariti_pass is False
    assert results[0].overall_pass is False


def test_common_ground_match_blocks() -> None:
    """When the slot is already common-ground, not_common_ground_pass is False."""
    c = Candidate(slot="Database engine", question="What DB?")
    sources = {"harness.yaml": {"Database engine": "postgres"}}
    results = apply_inequality_gate([c], sources, _cfg(), eig_mechanism=_high_eig)
    assert results[0].not_common_ground_pass is False
    assert results[0].common_ground_mark is not None
    assert results[0].overall_pass is False


def test_confidence_at_or_above_tau_blocks() -> None:
    """confidence >= τ fails the confidence term (gate asks for < τ)."""
    c = Candidate(slot="X", question="Q?", confidence=0.7)
    results = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)
    assert results[0].confidence_pass is False
    assert results[0].overall_pass is False


def test_confidence_just_below_tau_passes() -> None:
    """confidence < τ passes the confidence term."""
    c = Candidate(slot="X", question="Q?", confidence=0.69)
    results = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)
    assert results[0].confidence_pass is True


def test_clariti_exact_boundary_passes() -> None:
    """CLARITI uses >= comparison: 1.0 × 0.7 = 0.7 exactly passes."""
    c = Candidate(slot="X", question="Q?", task_relevance=1.0, user_answerability=0.7)
    results = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)
    assert results[0].clariti_pass is True


def test_clariti_just_below_boundary_blocks() -> None:
    """CLARITI: 1.0 × 0.699 ≈ 0.699 < 0.7 → fails (guards >= vs > regression)."""
    c = Candidate(slot="X", question="Q?", task_relevance=1.0, user_answerability=0.699)
    results = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)
    assert results[0].clariti_pass is False


def test_mixed_open_closed_cap_ordering_invariant() -> None:
    """Reviewer-caught bug guard: mixed open + closed inputs with cap demotion
    must still produce passes-first ordering. Without the post-demotion re-sort,
    a cap-demoted open-ended candidate would interleave between closed passes."""
    candidates = [
        Candidate(slot="open-A", question="qa", is_open_ended=True),
        Candidate(slot="open-B", question="qb", is_open_ended=True),
        Candidate(slot="closed-C", question="qc", is_open_ended=False),
        Candidate(slot="open-D", question="qd", is_open_ended=True),  # cap-demoted
        Candidate(slot="closed-E", question="qe", is_open_ended=False),
    ]
    scores = {"qa": 0.9, "qb": 0.8, "qc": 0.75, "qd": 0.7, "qe": 0.65}
    results = apply_inequality_gate(
        candidates, {}, _cfg(), eig_mechanism=_q_specific_eig(scores), locale="en"
    )
    first_fail = next((i for i, r in enumerate(results) if not r.overall_pass), len(results))
    later = results[first_fail:]
    assert all(not r.overall_pass for r in later), (
        f"passes-first ordering broken: {[(r.candidate.slot, r.overall_pass) for r in results]}"
    )
    open_d_idx = next(i for i, r in enumerate(results) if r.candidate.slot == "open-D")
    closed_e_idx = next(i for i, r in enumerate(results) if r.candidate.slot == "closed-E")
    assert closed_e_idx < open_d_idx, "closed-E (pass) must precede open-D (cap-demoted)"


# ---------- Ranking order ---------------------------------------------------------------


def test_passes_sorted_before_failures() -> None:
    """overall_pass=True candidates rank before overall_pass=False ones."""
    pass_c = Candidate(slot="A", question="passing-Q")
    fail_c = Candidate(slot="B", question="failing-Q", task_relevance=0.1)
    results = apply_inequality_gate([fail_c, pass_c], {}, _cfg(), eig_mechanism=_high_eig)
    assert results[0].candidate.slot == "A"  # the passing one comes first
    assert results[1].candidate.slot == "B"


def test_ties_broken_by_eig_descending() -> None:
    """Within the same pass-status, higher EIG ranks first."""
    a = Candidate(slot="A", question="q-A")
    b = Candidate(slot="B", question="q-B")
    c = Candidate(slot="C", question="q-C")
    scores = {"q-A": 0.6, "q-B": 0.95, "q-C": 0.75}
    results = apply_inequality_gate([a, b, c], {}, _cfg(), eig_mechanism=_q_specific_eig(scores))
    ranked_slots = [r.candidate.slot for r in results]
    assert ranked_slots == ["B", "C", "A"]


def test_stable_sort_preserves_input_order_on_full_tie() -> None:
    """Python's sort is stable — identical EIG keeps input order."""
    a = Candidate(slot="A", question="q-A")
    b = Candidate(slot="B", question="q-B")
    c = Candidate(slot="C", question="q-C")
    # All same EIG = full tie among passes.
    results = apply_inequality_gate([a, b, c], {}, _cfg(), eig_mechanism=_high_eig)
    assert [r.candidate.slot for r in results] == ["A", "B", "C"]


# ---------- Locale cap enforcement -----------------------------------------------------


def test_locale_cap_en_2() -> None:
    """en locale allows 2 open-ended passes; the 3rd is demoted."""
    candidates = [
        Candidate(slot=f"open-{i}", question=f"Q-{i}", is_open_ended=True) for i in range(3)
    ]
    results = apply_inequality_gate(candidates, {}, _cfg(), eig_mechanism=_high_eig, locale="en")
    open_passing = [r for r in results if r.overall_pass and r.candidate.is_open_ended]
    assert len(open_passing) == 2
    # Third was demoted.
    demoted = [r for r in results if r.candidate.is_open_ended and not r.open_ended_pass]
    assert len(demoted) == 1


def test_locale_cap_ko_1() -> None:
    """ko locale caps open-ended at 1 (matches '직접적' user-feedback memory)."""
    candidates = [
        Candidate(slot=f"open-{i}", question=f"Q-{i}", is_open_ended=True) for i in range(3)
    ]
    results = apply_inequality_gate(candidates, {}, _cfg(), eig_mechanism=_high_eig, locale="ko")
    open_passing = [r for r in results if r.overall_pass and r.candidate.is_open_ended]
    assert len(open_passing) == 1


def test_locale_cap_ja_1() -> None:
    """ja locale caps open-ended at 1 (parallel with ko)."""
    candidates = [Candidate(slot=f"o-{i}", question=f"Q-{i}", is_open_ended=True) for i in range(2)]
    results = apply_inequality_gate(candidates, {}, _cfg(), eig_mechanism=_high_eig, locale="ja")
    assert sum(1 for r in results if r.overall_pass and r.candidate.is_open_ended) == 1


def test_locale_unknown_falls_back_to_default_cap() -> None:
    """Unknown locale uses the 'default' cap (1)."""
    candidates = [Candidate(slot=f"o-{i}", question=f"Q-{i}", is_open_ended=True) for i in range(2)]
    results = apply_inequality_gate(candidates, {}, _cfg(), eig_mechanism=_high_eig, locale="zh")
    assert sum(1 for r in results if r.overall_pass and r.candidate.is_open_ended) == 1


def test_closed_questions_do_not_count_toward_cap() -> None:
    """Non-open-ended candidates pass freely — cap restricts only is_open_ended=True."""
    candidates = [
        Candidate(slot=f"closed-{i}", question=f"q-c-{i}", is_open_ended=False) for i in range(5)
    ]
    results = apply_inequality_gate(candidates, {}, _cfg(), eig_mechanism=_high_eig, locale="ko")
    assert all(r.overall_pass for r in results)


def test_cap_demotion_keeps_other_terms_true() -> None:
    """A demoted open-ended candidate retains its term-specific pass flags."""
    candidates = [Candidate(slot=f"o-{i}", question=f"Q-{i}", is_open_ended=True) for i in range(3)]
    results = apply_inequality_gate(candidates, {}, _cfg(), eig_mechanism=_high_eig, locale="en")
    demoted = [r for r in results if not r.open_ended_pass]
    assert len(demoted) == 1
    r = demoted[0]
    # All other terms still True — only open_ended_pass flipped.
    assert r.eig_pass is True
    assert r.clariti_pass is True
    assert r.not_common_ground_pass is True
    assert r.confidence_pass is True
    assert r.open_ended_pass is False
    assert r.overall_pass is False


# ---------- Edge cases -----------------------------------------------------------------


def test_zero_candidates_returns_empty_list() -> None:
    """An empty candidate list returns an empty result list."""
    results = apply_inequality_gate([], {}, _cfg(), eig_mechanism=_high_eig)
    assert results == []


def test_all_common_ground_blocks_all() -> None:
    """When every slot is common-ground, every candidate fails."""
    sources = {
        "harness.yaml": {
            "slot-A": "x",
            "slot-B": "y",
            "slot-C": "z",
        }
    }
    candidates = [Candidate(slot=f"slot-{x}", question=f"Q-{x}") for x in "ABC"]
    results = apply_inequality_gate(candidates, sources, _cfg(), eig_mechanism=_high_eig)
    assert all(not r.overall_pass for r in results)
    assert all(r.common_ground_mark is not None for r in results)


def test_all_low_eig_blocks_all() -> None:
    """When every candidate's EIG is below ε, every overall_pass is False."""
    candidates = [Candidate(slot=f"s-{i}", question=f"q-{i}") for i in range(3)]
    results = apply_inequality_gate([*candidates], {}, _cfg(), eig_mechanism=_low_eig)
    assert all(r.eig_pass is False for r in results)


def test_all_low_confidence_clearance_passes() -> None:
    """confidence=0 (default) easily beats τ; symmetrically all confidence terms pass."""
    candidates = [Candidate(slot=f"s-{i}", question=f"q-{i}") for i in range(3)]
    results = apply_inequality_gate([*candidates], {}, _cfg(), eig_mechanism=_high_eig)
    assert all(r.confidence_pass for r in results)


def test_accumulator_collects_common_ground_marks() -> None:
    """Caller-supplied accumulator receives marks from common_ground hits."""
    accum: list[CGMark] = []
    candidates = [Candidate(slot="DB", question="What DB?")]
    apply_inequality_gate(
        candidates,
        {"harness.yaml": {"DB": "postgres"}},
        _cfg(),
        eig_mechanism=_high_eig,
        accumulator=accum,
    )
    assert len(accum) == 1
    assert accum[0].slot == "DB"


# ---------- ADR-005 checklist rendering ------------------------------------------------


def test_checklist_summary_all_pass() -> None:
    """All-pass candidate renders ✅×5, '5/5 met (PASS)'."""
    c = Candidate(slot="X", question="Q")
    r = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)[0]
    assert "5/5 met (PASS)" in r.checklist_summary
    assert "❌" not in r.checklist_summary


def test_checklist_summary_partial() -> None:
    """A candidate that fails one term renders '4/5 met (NEEDS)'."""
    c = Candidate(slot="X", question="Q", confidence=0.8)
    r = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)[0]
    assert "4/5 met (NEEDS)" in r.checklist_summary
    assert "❌ confidence" in r.checklist_summary


def test_checklist_includes_all_5_term_labels() -> None:
    """The 5-term checklist names every term."""
    c = Candidate(slot="X", question="Q")
    r = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)[0]
    for label in ("EIG", "CLARITI", "common-ground", "confidence", "open-ended"):
        assert label in r.checklist_summary


# ---------- GateConfig defaults --------------------------------------------------------


def test_gate_config_defaults_match_adrs() -> None:
    """Defaults align with ADR-007 (ε=0.5, τ=0.7) + ADR-003 (cg threshold 0.95)."""
    cfg = GateConfig()
    assert cfg.eig_epsilon == 0.5
    assert cfg.confidence_tau == 0.7
    assert cfg.llm_inference_threshold == 0.95
    assert cfg.llm_inference_enabled is True
    assert cfg.clariti_threshold == 0.7
    assert cfg.open_ended_cap_by_locale == {"en": 2, "ko": 1, "ja": 1, "default": 1}


def test_cap_for_locale_helper() -> None:
    """cap_for_locale returns the per-locale value or 'default' fallback."""
    cfg = GateConfig()
    assert cfg.cap_for_locale("en") == 2
    assert cfg.cap_for_locale("ko") == 1
    assert cfg.cap_for_locale("ja") == 1
    assert cfg.cap_for_locale("xx") == 1  # default


# ---------- GateResult is frozen -------------------------------------------------------


def test_gate_result_frozen() -> None:
    """GateResult is a frozen dataclass — accidental mutation impossible."""
    c = Candidate(slot="X", question="Q")
    r = apply_inequality_gate([c], {}, _cfg(), eig_mechanism=_high_eig)[0]
    with pytest.raises(AttributeError):
        r.eig_pass = False  # type: ignore[misc]
