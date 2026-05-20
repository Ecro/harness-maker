"""Tests for spec_mutation (P1, ADR-005)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker.spec_mutation import (
    PLUS_DELTA_PP,
    TIER_FLOORS,
    MutationReport,
    gate,
    measure_baseline,
    report_to_json,
    threshold_for,
)


def test_tier_floors_correct() -> None:
    assert TIER_FLOORS[1] == 85
    assert TIER_FLOORS[2] == 70
    assert TIER_FLOORS[3] is None  # informational, non-gating


def test_plus_delta_pp_is_5() -> None:
    assert PLUS_DELTA_PP == 5


def test_threshold_t1_no_baseline_uses_floor() -> None:
    assert threshold_for(1, None) == 85


def test_threshold_t2_no_baseline_uses_floor() -> None:
    assert threshold_for(2, None) == 70


def test_threshold_t3_no_gate() -> None:
    assert threshold_for(3, None) is None
    assert threshold_for(3, 0.95) is None


def test_threshold_baseline_relative_above_floor() -> None:
    # baseline 90% → threshold = max(95, 85) = 95
    assert threshold_for(1, 0.90) == 95


def test_threshold_baseline_below_floor_clamps_to_floor() -> None:
    # baseline 50% → max(55, 85) = 85
    assert threshold_for(1, 0.50) == 85


def test_threshold_accepts_pct_or_fraction() -> None:
    # 0.65 → 70 = 65+5; 65 → 85 = max(70, 85); both ok
    assert threshold_for(1, 0.65) == 85
    # already-percent baseline (>1) also accepted
    assert threshold_for(1, 90) == 95  # max(95, 85)


def test_gate_t3_always_passes() -> None:
    rep = MutationReport(
        paths=("x.py",),
        killed=0,
        survived=10,
        timeout=0,
        suspicious=0,
        skipped=0,
        sampled=False,
        raw_output="",
    )
    passes, _ = gate(rep, 3, baseline=None)
    assert passes is True


def test_gate_score_meets_threshold() -> None:
    rep = MutationReport(
        paths=("x.py",),
        killed=85,
        survived=15,
        timeout=0,
        suspicious=0,
        skipped=0,
        sampled=False,
        raw_output="",
    )
    passes, reason = gate(rep, 1, baseline=None)
    assert passes is True
    assert "85" in reason


def test_gate_score_below_threshold() -> None:
    rep = MutationReport(
        paths=("x.py",),
        killed=70,
        survived=30,
        timeout=0,
        suspicious=0,
        skipped=0,
        sampled=False,
        raw_output="",
    )
    passes, reason = gate(rep, 1, baseline=None)
    assert passes is False


def test_mutation_report_score_zero_for_empty() -> None:
    rep = MutationReport(
        paths=(),
        killed=0,
        survived=0,
        timeout=0,
        suspicious=0,
        skipped=0,
        sampled=False,
        raw_output="",
    )
    assert rep.score == 0.0


def test_mutation_report_total_counts() -> None:
    rep = MutationReport(
        paths=("x.py",),
        killed=10,
        survived=5,
        timeout=2,
        suspicious=1,
        skipped=0,
        sampled=False,
        raw_output="",
    )
    assert rep.total == 18


def test_report_to_json_round_trip() -> None:
    rep = MutationReport(
        paths=("x.py",),
        killed=85,
        survived=15,
        timeout=0,
        suspicious=0,
        skipped=0,
        sampled=False,
        raw_output="",
    )
    blob = report_to_json(rep)
    data = json.loads(blob)
    assert data["paths"] == ["x.py"]
    assert data["killed"] == 85
    assert data["score"] == pytest.approx(0.85, abs=1e-4)


def test_measure_baseline_no_paths_returns_zero(tmp_path: Path) -> None:
    rep = measure_baseline([], cwd=tmp_path)
    assert rep.total == 0


def test_measure_baseline_mutmut_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When mutmut is not installed, wrapper returns a zero-counter report.

    REVIEW T-P1-B: prior implementation declared monkeypatch but never used
    it, so the test was a no-op that passed regardless of mutmut presence.
    Now we deterministically replace subprocess.run with a FileNotFoundError
    raiser and assert the documented empty-state contract.
    """
    import harness_maker.spec_mutation as sm

    def _raise_fnf(*_a: Any, **_kw: Any) -> None:
        raise FileNotFoundError("mutmut: not installed (mocked)")

    monkeypatch.setattr(sm.subprocess, "run", _raise_fnf)

    rep = measure_baseline(
        ["src/harness_maker/render.py"],
        cwd=tmp_path,
        timeout_seconds=1,
    )
    assert isinstance(rep, MutationReport)
    assert rep.killed == 0
    assert rep.survived == 0
    assert rep.total == 0
    assert rep.score == 0.0
    assert rep.paths == ("src/harness_maker/render.py",)


def test_measure_baseline_timeout_preserves_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TimeoutExpired keeps partial stdout/stderr (REVIEW C-P1-E).

    Without this, a long mutmut run that completes 200/250 mutants returns a
    0% score after timeout — spuriously failing the gate.
    """
    import harness_maker.spec_mutation as sm

    def _raise_timeout(*_a: Any, **_kw: Any) -> None:
        raise subprocess.TimeoutExpired(
            cmd=["mutmut"],
            timeout=10,
            output=b"killed: 80\nsurvived: 20\n",
            stderr=b"",
        )

    monkeypatch.setattr(sm.subprocess, "run", _raise_timeout)

    rep = measure_baseline(["src/x.py"], cwd=tmp_path, timeout_seconds=10)
    # Partial output must be parsed — not zeroed.
    assert rep.killed == 80
    assert rep.survived == 20
    assert rep.score == pytest.approx(0.80)
