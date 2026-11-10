"""Phase 6 — AC-010, AC-011, AC-014, AC-019: the gate, the single dispatch, the exits.

This is the only phase that REMOVES a review that happens today, so each test below is
written against the wrong implementation it rejects rather than against the happy path.
The AC-010 rows come from the machine SPEC's golden table, never inlined — an earlier
copy of these four rows lived in `test_review_consensus.py` as literals and could drift
from the SPEC without anything going red.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.readiness import churn_gate_signal
from harness_maker.spec_machine import load_golden_table
from tests.stage_surface import stage_text

_SPEC = Path(__file__).parents[2] / "specs" / "SPEC-review-loop-empirics.machine.yaml"
_ROWS = load_golden_table(_SPEC, "AC-010")


# ── AC-014 — the stalled loop ────────────────────────────────────────────────


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
    out = Path(tempfile.mkdtemp()) / ".claude"
    render(synthesize(profile, answers), out, freeze_time=DEFAULT_FREEZE_TIME)
    return stage_text(out, "review")
