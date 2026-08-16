"""Phase 6 — AC-010, AC-011, AC-014, AC-019: the gate, the single dispatch, the exits.

This is the only phase that REMOVES a review that happens today, so each test below is
written against the wrong implementation it rejects rather than against the happy path.
The AC-010 rows come from the machine SPEC's golden table, never inlined — an earlier
copy of these four rows lived in `test_review_consensus.py` as literals and could drift
from the SPEC without anything going red.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.readiness import churn_gate_signal
from harness_maker.review_churn import resolve_churn_threshold
from harness_maker.review_consensus import exit_record, rereview_plan, rereview_reason
from harness_maker.spec_machine import GoldenRow, load_golden_table

_SPEC = Path(__file__).parents[2] / "specs" / "SPEC-review-loop-empirics.machine.yaml"
_ROWS = load_golden_table(_SPEC, "AC-010")


@pytest.mark.parametrize(
    "row", _ROWS, ids=[f"{r.input['churn_ratio']}-vs-{r.input['threshold']}" for r in _ROWS]
)
def test_below_threshold_churn_skips_rereview(row: GoldenRow) -> None:
    """Both halves: the dispatch count AND the recorded reason.

    Counting dispatches alone accepts a gate that skips silently — and a skip whose
    reason is not recorded is indistinguishable, later, from a round where no reviewer
    was scoped in the first place.
    """
    ratio = float(row.input["churn_ratio"])
    threshold = float(row.input["threshold"])
    plan = rereview_plan(ratio, threshold)
    assert len(plan) == row.expected["dispatches"]

    reason = rereview_reason(ratio, threshold)
    assert row.expected["reason_contains"] in reason
    for dispatch in plan:
        assert dispatch.reason == reason


def test_above_threshold_dispatches_one_structured_reviewer() -> None:
    """One, and it carries a lens — "some reviewer" is not a structured dispatch."""
    plan = rereview_plan(churn_ratio=0.35, threshold=resolve_churn_threshold({}))
    assert len(plan) == 1
    assert plan[0].agent
    assert plan[0].lens


def test_below_threshold_churn_skips_rereview_at_the_configured_threshold_not_the_default() -> None:
    """A gate hardcoding 0.20 passes every default-config test and ignores the key.

    `rereview_churn_ratio: 0.5` is the configured statement "half a file is where
    re-review starts"; a 0.35 round must skip under it and dispatch under the default.
    """
    configured = resolve_churn_threshold({"rereview_churn_ratio": 0.5})
    assert rereview_plan(0.35, configured) == []
    assert len(rereview_plan(0.35, resolve_churn_threshold({}))) == 1


# ── AC-014 — the stalled loop ────────────────────────────────────────────────


def test_no_progress_records_churn_ratio() -> None:
    record = exit_record(transitions=0, churn_ratio=0.0)
    assert record["exit_reason"] == "no-progress"
    assert record["churn_ratio"] == 0.0


def test_no_progress_records_churn_ratio_even_when_nothing_was_measurable() -> None:
    """The key is always present; absent-vs-zero is the distinction it carries."""
    record = exit_record(transitions=0, churn_ratio=None)
    assert record["exit_reason"] == "no-progress"
    assert record["churn_ratio"] is None


def test_no_progress_records_churn_ratio_without_disturbing_exit_precedence() -> None:
    """The pre-change assignment for the same inputs, unchanged (AC-014's oracle).

    Each row names a stop that is ALSO no-progress by the raw transition count; the
    label that wins is the shipped one. `cap-exhausted` in particular must never be
    reported for a stop the no-progress invariant made.
    """
    assert exit_record(transitions=0, churn_ratio=0.1, approved=True)["exit_reason"] == "converged"
    assert (
        exit_record(transitions=0, churn_ratio=0.1, auto_fix=False)["exit_reason"]
        == "auto-fix-disabled"
    )
    assert (
        exit_record(transitions=0, churn_ratio=0.1, rounds_used=3, max_rounds=3)["exit_reason"]
        == "no-progress"
    )
    assert (
        exit_record(transitions=2, churn_ratio=0.1, rounds_used=3, max_rounds=3)["exit_reason"]
        == "cap-exhausted"
    )


def test_exit_record_refuses_to_label_a_round_that_has_not_stopped() -> None:
    """A fallthrough label would be written into an append-only record as a real exit."""
    with pytest.raises(ValueError, match="has not stopped"):
        exit_record(transitions=2, churn_ratio=0.1, rounds_used=1, max_rounds=3)


# ── AC-019 — /hm:health on a disabled gate ───────────────────────────────────


def test_health_reports_gate_off_as_not_applicable() -> None:
    """All three properties: `not_applicable`, `passed=True`, and no penalty.

    Asserting `passed` alone accepts a signal that quietly costs the harness points for
    a configuration choice the user made deliberately — the same shape already settled
    for `permissions.deny_dangerous`.
    """
    signal = churn_gate_signal(enabled=False)
    assert signal.not_applicable is True
    assert signal.passed is True
    assert signal.weight == 0
    assert signal.action is None


def test_health_reports_an_enabled_gate_as_applicable() -> None:
    """Non-vacuity: `not_applicable` must not be True for every input."""
    signal = churn_gate_signal(enabled=True)
    assert signal.not_applicable is False
    assert signal.passed is True


def test_health_fails_a_malformed_threshold_rather_than_defaulting_it() -> None:
    """A typo'd ratio decides whether reviews happen; silently defaulting it hides that."""
    signal = churn_gate_signal(enabled=True, reviewers={"rereview_churn_ratio": "twenty"})
    assert signal.not_applicable is False
    assert signal.passed is False
    assert signal.action


# ── the rendered stage: the gate branch, both settings ───────────────────────


def _render_review(*, gate: bool) -> str:
    import tempfile

    from harness_maker.interview import interview
    from harness_maker.models import ProjectProfile
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    profile = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    answers = interview(profile, autoloop_mode=True)
    answers.rereview_churn_gate = gate
    out = Path(tempfile.mkdtemp())
    render(synthesize(profile, answers), out, freeze_time=DEFAULT_FREEZE_TIME)
    return (out / "commands" / "hm" / "review.md").read_text(encoding="utf-8")


def test_below_threshold_churn_skips_rereview_is_wired_into_the_rendered_stage() -> None:
    """Arithmetic nothing calls decides nothing (the round-1 P0 of this PLAN, verbatim)."""
    body = _render_review(gate=True)
    calls = [ln for ln in body.splitlines() if "hm review_consensus plan " in ln]
    assert len(calls) == 1, f"expected one plan invocation, got {len(calls)}"
    assert "--churn-ratio" in calls[0]
    assert "--threshold" in calls[0]


def test_the_gate_off_render_keeps_the_scope_selected_reviewer_set() -> None:
    """The rollback in `rereview_churn_gate: false` has to actually restore the old text.

    This is the only phase that removes a review that happens today; if the off-render
    silently kept the gate, the escape hatch documented in `harness.yaml` would be a lie.
    """
    body = _render_review(gate=False)
    assert "re-spawn ONLY reviewers whose scope was touched" in body
    assert "hm review_consensus plan " not in body
    assert "dispatch nobody" not in body.lower()


def test_the_gate_on_render_states_the_unmeasurable_case_explicitly() -> None:
    """The absent case is this repo's most-recurring failure class (count:8).

    A null ratio must re-review, not skip. Without the branch the natural reading of
    "below the threshold" swallows null and the gate skips every round it could not
    measure — the exact silent no-op the learned correction describes.
    """
    body = _render_review(gate=True)
    assert "null" in body
    gated = body[body.index("Re-review (gated") :][:2000]
    assert "as if the gate were off" in gated


def test_both_renders_count_every_fix_in_a_skipped_round_as_unreviewed() -> None:
    """The skip's cost must stay visible in the terminal measure, gate on or off."""
    for gate in (True, False):
        assert "`unreviewed_fix_count` = applied fixes" in _render_review(gate=gate)
