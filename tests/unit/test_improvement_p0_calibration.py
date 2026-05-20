"""PLAN-fresh-install-p0-calibration unit tests for _extract_layer1_actions.

Verifies the two-branch policy applied to INTENDED_P0_SIGNALS:
  - TELEMETRY_AUTO_RESOLVE_SIGNALS (metrics_jsonl_present, metrics_has_samples):
    suppressed when metrics_has_samples.passed is False (samples < 5).
  - USER_AUTHOR_SIGNALS (adr_present, contributing_present, ci_workflow_present):
    priority overridden to "P2" regardless of weight.
  - Other (non-INTENDED) failing signals: priority via _layer1_priority(weight).

Counters returned alongside the action list power the CLI footer (ADR-004).
"""

from __future__ import annotations

from harness_maker.improvement import (
    ImprovementPlan,
    _extract_layer1_actions,
    build_improvement_plan,
)
from harness_maker.readiness import (
    DimensionScore,
    ReadinessResult,
    Signal,
)


def _sig(sig_id: str, passed: bool, weight: int = 25) -> Signal:
    return Signal(
        id=sig_id,
        passed=passed,
        weight=weight,
        evidence=f"evidence for {sig_id}",
        action=None if passed else f"do the {sig_id} thing",
    )


def _dim(name: str, signals: list[Signal]) -> DimensionScore:
    earned = sum(s.weight for s in signals if s.passed)
    return DimensionScore(name=name, score=max(0, min(100, earned)), signals=signals)


def _readiness(
    *,
    observability_signals: list[Signal] | None = None,
    governance_signals: list[Signal] | None = None,
    verification_signals: list[Signal] | None = None,
    extras: dict[str, DimensionScore] | None = None,
    preset: str = "Production",
) -> ReadinessResult:
    dims: dict[str, DimensionScore] = {}
    if observability_signals is not None:
        dims["observability_setup"] = _dim("observability_setup", observability_signals)
    if governance_signals is not None:
        dims["governance"] = _dim("governance", governance_signals)
    if verification_signals is not None:
        dims["verification"] = _dim("verification", verification_signals)
    if extras:
        dims.update(extras)
    weights = {name: 1.0 / max(1, len(dims)) for name in dims}
    if "governance" in weights and preset == "Production":
        # Mirror real Production weighting — non-zero.
        weights["governance"] = 0.05
    return ReadinessResult(
        preset=preset,
        dimensions=dims,
        weights=weights,
        ceremony_penalty=0.0,
        user_md_files=0,
        composite=50,
    )


# ── Telemetry suppression ──────────────────────────────────────────────────


def test_telemetry_suppressed_when_samples_below_threshold() -> None:
    """Fresh install: metrics_has_samples.passed=False → both telemetry signals suppressed."""
    obs_signals = [
        _sig("metrics_jsonl_present", passed=False, weight=25),
        _sig("metrics_has_samples", passed=False, weight=25),
    ]
    readiness = _readiness(observability_signals=obs_signals)

    actions, deferred_telemetry, demoted_governance = _extract_layer1_actions(readiness)

    telemetry_actions = [a for a in actions if a.source.startswith("layer1:metrics_")]
    assert telemetry_actions == [], "telemetry signals must be hidden on fresh install"
    assert deferred_telemetry == 2
    assert demoted_governance == 0


def test_telemetry_surfaces_at_samples_threshold() -> None:
    """Steady state: metrics_has_samples.passed=True → telemetry signal failures surface as P0.

    This guards against the dangerous opposite — once telemetry has been
    collected (samples ≥ 5), a genuine regression that stops new entries
    MUST still alert the user. The suppression rule applies ONLY pre-threshold.
    """
    obs_signals = [
        _sig("metrics_jsonl_present", passed=False, weight=25),
        _sig("metrics_has_samples", passed=True, weight=25),
    ]
    readiness = _readiness(observability_signals=obs_signals)

    actions, deferred_telemetry, _ = _extract_layer1_actions(readiness)

    telemetry_actions = [a for a in actions if a.source == "layer1:metrics_jsonl_present"]
    assert len(telemetry_actions) == 1
    assert telemetry_actions[0].priority == "P0"
    assert deferred_telemetry == 0


# ── Governance override ────────────────────────────────────────────────────


def test_adr_present_demoted_to_p2() -> None:
    """adr_present (weight 50) → would be P0 normally; INTENDED override forces P2."""
    gov_signals = [
        _sig("adr_present", passed=False, weight=50),
    ]
    readiness = _readiness(governance_signals=gov_signals)

    actions, _, demoted_governance = _extract_layer1_actions(readiness)

    adr_actions = [a for a in actions if a.source == "layer1:adr_present"]
    assert len(adr_actions) == 1
    assert adr_actions[0].priority == "P2", "ADR demotion overrides P0 weight"
    assert demoted_governance == 1


def test_contributing_present_demoted_to_p2() -> None:
    """contributing_present (weight 50) → P0 normally; override to P2."""
    gov_signals = [
        _sig("contributing_present", passed=False, weight=50),
    ]
    readiness = _readiness(governance_signals=gov_signals)

    actions, _, demoted_governance = _extract_layer1_actions(readiness)

    contributing_actions = [a for a in actions if a.source == "layer1:contributing_present"]
    assert len(contributing_actions) == 1
    assert contributing_actions[0].priority == "P2"
    assert demoted_governance == 1


def test_ci_workflow_present_demoted_to_p2() -> None:
    """ci_workflow_present (weight 20) → P1 normally; override to P2."""
    ver_signals = [
        _sig("ci_workflow_present", passed=False, weight=20),
    ]
    readiness = _readiness(verification_signals=ver_signals)

    actions, _, demoted_governance = _extract_layer1_actions(readiness)

    ci_actions = [a for a in actions if a.source == "layer1:ci_workflow_present"]
    assert len(ci_actions) == 1
    assert ci_actions[0].priority == "P2"
    assert demoted_governance == 1


# ── Combined / control ─────────────────────────────────────────────────────


def test_fresh_install_full_scenario() -> None:
    """Full fresh-install fixture: telemetry suppressed + governance demoted."""
    obs_signals = [
        _sig("observability_dir_present", passed=False, weight=25),
        _sig("metrics_jsonl_present", passed=False, weight=25),
        _sig("metrics_has_samples", passed=False, weight=25),
        _sig("dashboard_md_present", passed=False, weight=25),
    ]
    gov_signals = [
        _sig("adr_present", passed=False, weight=50),
        _sig("contributing_present", passed=False, weight=50),
    ]
    ver_signals = [
        _sig("ci_workflow_present", passed=False, weight=20),
        _sig("ci_invokes_tests", passed=False, weight=20),  # NOT in INTENDED
    ]
    readiness = _readiness(
        observability_signals=obs_signals,
        governance_signals=gov_signals,
        verification_signals=ver_signals,
    )

    actions, deferred_telemetry, demoted_governance = _extract_layer1_actions(readiness)

    sources = {a.source for a in actions}
    # Telemetry suppressed
    assert "layer1:metrics_jsonl_present" not in sources
    assert "layer1:metrics_has_samples" not in sources
    # Governance + CI surfaced as P2
    by_source = {a.source: a for a in actions}
    assert by_source["layer1:adr_present"].priority == "P2"
    assert by_source["layer1:contributing_present"].priority == "P2"
    assert by_source["layer1:ci_workflow_present"].priority == "P2"
    # ci_invokes_tests is NOT in INTENDED → keeps weight-derived priority (20 → P1)
    assert by_source["layer1:ci_invokes_tests"].priority == "P1"
    # Other failing signals (observability_dir_present, dashboard_md_present) → weight 25 → P0
    assert by_source["layer1:observability_dir_present"].priority == "P0"
    assert by_source["layer1:dashboard_md_present"].priority == "P0"

    assert deferred_telemetry == 2
    assert demoted_governance == 3


def test_non_intended_signal_priority_unchanged() -> None:
    """Control: a non-INTENDED failing signal preserves weight-derived priority."""
    custom_dim = _dim("custom", [_sig("custom_thing", passed=False, weight=30)])
    readiness = _readiness(extras={"custom": custom_dim})

    actions, deferred_telemetry, demoted_governance = _extract_layer1_actions(readiness)

    assert len(actions) == 1
    assert actions[0].priority == "P0"
    assert deferred_telemetry == 0
    assert demoted_governance == 0


def test_passing_signals_produce_no_actions() -> None:
    """Healthy project: all signals pass → empty action list, zero counters."""
    obs_signals = [
        _sig("metrics_jsonl_present", passed=True, weight=25),
        _sig("metrics_has_samples", passed=True, weight=25),
    ]
    gov_signals = [
        _sig("adr_present", passed=True, weight=50),
        _sig("contributing_present", passed=True, weight=50),
    ]
    readiness = _readiness(
        observability_signals=obs_signals,
        governance_signals=gov_signals,
    )

    actions, deferred_telemetry, demoted_governance = _extract_layer1_actions(readiness)
    assert actions == []
    assert deferred_telemetry == 0
    assert demoted_governance == 0


# ── ImprovementPlan exposes counters ──────────────────────────────────────


def test_improvement_plan_carries_counters() -> None:
    """build_improvement_plan propagates the deferred/demoted counts to the plan."""
    from harness_maker.cache_diagnostics import CacheDiagnosis

    obs_signals = [
        _sig("metrics_jsonl_present", passed=False, weight=25),
        _sig("metrics_has_samples", passed=False, weight=25),
    ]
    gov_signals = [
        _sig("adr_present", passed=False, weight=50),
    ]
    readiness = _readiness(observability_signals=obs_signals, governance_signals=gov_signals)
    cache = CacheDiagnosis(
        hit_rate=0,
        score=50,
        sample_size=0,
        primary_failure="no_data",
        evidence="no data",
        remediation="install hook",
        counters={},
    )

    plan = build_improvement_plan(readiness, [], cache)
    assert isinstance(plan, ImprovementPlan)
    assert plan.deferred_telemetry == 2
    assert plan.demoted_governance == 1


# ── Side preset: governance still skipped (regression guard) ──────────────


def test_governance_dim_skipped_on_side_preset() -> None:
    """Side preset's existing weight-zero governance skip path is unchanged.

    The new override only kicks in when the governance dimension is actually
    iterated (i.e. weight > 0). On Side, the dim is skipped before signal
    inspection, so no governance actions surface at all.
    """
    gov_signals = [
        _sig("adr_present", passed=False, weight=50),
    ]
    readiness = ReadinessResult(
        preset="Side",
        dimensions={"governance": _dim("governance", gov_signals)},
        weights={"governance": 0.0},
        ceremony_penalty=0.0,
        user_md_files=0,
        composite=50,
    )

    actions, _, demoted_governance = _extract_layer1_actions(readiness)

    assert [a for a in actions if a.dimension == "governance"] == []
    assert demoted_governance == 0
