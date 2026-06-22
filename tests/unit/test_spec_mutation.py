"""Tests for spec_mutation (P1, ADR-005)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker.spec_mutation import (
    EQUIVALENCE_RULES,
    PLUS_DELTA_PP,
    TIER_FLOORS,
    AdjustedScore,
    GrowthVerdict,
    MutantDescriptor,
    MutationReport,
    adjusted_score,
    baseline_to_json,
    classify_survivor,
    classify_survivors,
    detect_exclusion_growth,
    gate,
    load_baseline,
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


# ---------------------------------------------------------------------------
# CLI gate (PLAN-spec-test-accumulation — execute Phase D T1 gate)
# ---------------------------------------------------------------------------


def _write_machine(tmp_path: Path, *, paths: list[str], tier: int = 1) -> Path:
    import yaml

    data = {
        "schema_version": 1,
        "spec_slug": "demo",
        "verification_tier": tier,
        "mutation_threshold": 85,
        "paths_to_mutate": paths,
        "ac": [
            {
                "id": "AC-001",
                "title": "t",
                "type": "mechanical",
                "test_ids": ["t::f"],
                "executable_predicate": "result == 1",
            }
        ],
    }
    p = tmp_path / "SPEC-demo.machine.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def _report(killed: int, survived: int, *, raw: str = "") -> MutationReport:
    return MutationReport(
        paths=("src/x.py",),
        killed=killed,
        survived=survived,
        timeout=0,
        suspicious=0,
        skipped=0,
        sampled=False,
        raw_output=raw or f"killed: {killed} survived: {survived}",
    )


def test_cli_gate_passes_when_score_above_floor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import harness_maker.spec_mutation as sm

    yp = _write_machine(tmp_path, paths=["src/x.py"])
    monkeypatch.setattr(sm, "measure_baseline", lambda *a, **k: _report(90, 5))  # 94%
    rc = sm.main(["gate", "--yaml", str(yp), "--tier", "1"])
    assert rc == 0


def test_cli_gate_fails_when_score_below_floor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import harness_maker.spec_mutation as sm

    yp = _write_machine(tmp_path, paths=["src/x.py"])
    monkeypatch.setattr(sm, "measure_baseline", lambda *a, **k: _report(50, 50))  # 50% < 85
    rc = sm.main(["gate", "--yaml", str(yp), "--tier", "1"])
    assert rc == 1


def test_cli_gate_degrades_when_mutmut_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """mutmut not installed → non-gating (exit 0) with a skip notice."""
    import harness_maker.spec_mutation as sm

    yp = _write_machine(tmp_path, paths=["src/x.py"])
    monkeypatch.setattr(
        sm, "measure_baseline", lambda *a, **k: _report(0, 0, raw="mutmut: command not found")
    )
    rc = sm.main(["gate", "--yaml", str(yp), "--tier", "1"])
    assert rc == 0
    assert "not installed" in capsys.readouterr().err


def test_cli_gate_no_paths_is_noop(tmp_path: Path) -> None:
    import harness_maker.spec_mutation as sm

    yp = _write_machine(tmp_path, paths=[])
    rc = sm.main(["gate", "--yaml", str(yp), "--tier", "1"])
    assert rc == 0


# ---------------------------------------------------------------------------
# Equivalent-mutant classifier (ADR-004, audited no-shrink denominator)
# ---------------------------------------------------------------------------


def test_equivalence_rules_have_stable_ids() -> None:
    ids = {r.rule_id for r in EQUIVALENCE_RULES}
    assert "typing-cast-string-noop" in ids
    assert "int-default-near-time" in ids
    # rule_ids are unique within the closed set
    assert len(ids) == len(EQUIVALENCE_RULES)


def test_classify_typing_cast_string_is_equivalent() -> None:
    d = MutantDescriptor(
        mutant_id="m1",
        source_line='x = cast("Foo", obj)',
        context='return cast("XXFooXX", obj)',
    )
    classification, rule_id = classify_survivor(d)
    assert classification == "equivalent"
    assert rule_id == "typing-cast-string-noop"


def test_cast_in_context_only_does_not_exclude() -> None:
    """REVIEW consensus P2 / Codex-high: an unrelated cast() in CONTEXT must not
    classify a real survivor (mutated source_line) as equivalent."""
    d = MutantDescriptor(
        mutant_id="real",
        source_line="total = a - b",  # the real mutation, NOT a cast
        context='x = cast("T", v)',  # unrelated cast nearby
    )
    classification, rule_id = classify_survivor(d)
    assert classification == "pending-review"
    assert rule_id is None


def test_int_default_in_context_only_does_not_exclude() -> None:
    """REVIEW consensus P2: the .get(k,N) default must be on the mutated source_line."""
    d = MutantDescriptor(
        mutant_id="real2",
        source_line="total = a - b",  # the real mutation
        context="started = data.get(k, 0)\nelapsed = time.time() - started",
    )
    classification, rule_id = classify_survivor(d)
    assert classification == "pending-review"
    assert rule_id is None


def test_classify_typing_cast_qualified_is_equivalent() -> None:
    d = MutantDescriptor(
        mutant_id="m1b",
        source_line='y = typing.cast("Bar", v)',
        context="",
    )
    classification, rule_id = classify_survivor(d)
    assert classification == "equivalent"
    assert rule_id == "typing-cast-string-noop"


def test_classify_int_default_near_time_is_equivalent() -> None:
    d = MutantDescriptor(
        mutant_id="m2",
        source_line="started = data.get(key, 1)",
        context="elapsed = time.time() - data.get(key, 1)",
    )
    classification, rule_id = classify_survivor(d)
    assert classification == "equivalent"
    assert rule_id == "int-default-near-time"


def test_classify_unknown_survivor_is_pending_review() -> None:
    d = MutantDescriptor(
        mutant_id="m3",
        source_line="total = a + b",
        context="total = a - b",
    )
    classification, rule_id = classify_survivor(d)
    assert classification == "pending-review"
    assert rule_id is None


def test_classifier_never_returns_real_not_killed() -> None:
    # No descriptor input can make the classifier emit real-not-killed.
    for src in ("foo()", "x = cast(SomeType, v)", "data.get(k, 99)", "return 0"):
        classification, _ = classify_survivor(
            MutantDescriptor(mutant_id="x", source_line=src, context=src)
        )
        assert classification != "real-not-killed"


def test_classify_cast_without_string_first_arg_is_pending() -> None:
    # cast(SomeType, v) — first arg is NOT a string literal → not the no-op rule
    d = MutantDescriptor(
        mutant_id="m4",
        source_line="z = cast(SomeType, v)",
        context="",
    )
    classification, rule_id = classify_survivor(d)
    assert classification == "pending-review"
    assert rule_id is None


def test_adjusted_score_excludes_only_equivalent() -> None:
    # 80 killed, 20 survived; 5 of the survivors are rule-equivalent.
    rep = _report(80, 20)
    survivors = [
        MutantDescriptor(
            mutant_id=f"eq{i}",
            source_line='cast("T", v)',
            context="",
        )
        for i in range(5)
    ]
    survivors += [
        MutantDescriptor(mutant_id=f"pend{i}", source_line="a - b", context="") for i in range(15)
    ]
    result = adjusted_score(rep, survivors)
    assert isinstance(result, AdjustedScore)
    # denom = 100 - 5 excluded = 95; killed 80 → 80/95
    assert result.excluded_equivalent == 5
    assert result.score == pytest.approx(80 / 95)
    # excluded count is visible alongside the score
    assert result.killed == 80
    assert result.denominator == 95


def test_adjusted_score_pending_stays_in_denominator() -> None:
    # All survivors unknown → no exclusion → score == raw score.
    rep = _report(80, 20)
    survivors = [
        MutantDescriptor(mutant_id=f"p{i}", source_line="a - b", context="") for i in range(20)
    ]
    result = adjusted_score(rep, survivors)
    assert result.excluded_equivalent == 0
    assert result.denominator == 100
    assert result.score == pytest.approx(0.80)


def test_classify_survivors_persists_per_mutant() -> None:
    survivors = [
        MutantDescriptor(mutant_id="a", source_line='cast("T", v)', context=""),
        MutantDescriptor(mutant_id="b", source_line="x - y", context=""),
    ]
    classified = classify_survivors(survivors)
    by_id = {c.mutant_id: c for c in classified}
    assert by_id["a"].classification == "equivalent"
    assert by_id["a"].rule_id == "typing-cast-string-noop"
    assert by_id["b"].classification == "pending-review"
    assert by_id["b"].rule_id is None


def test_baseline_json_round_trip(tmp_path: Path) -> None:
    survivors = [
        MutantDescriptor(mutant_id="a", source_line='cast("T", v)', context=""),
        MutantDescriptor(mutant_id="b", source_line="x - y", context=""),
    ]
    classified = classify_survivors(survivors)
    blob = baseline_to_json(classified)
    data = json.loads(blob)
    assert {e["mutant_id"] for e in data["classifications"]} == {"a", "b"}

    p = tmp_path / "baseline.json"
    p.write_text(blob)
    loaded = load_baseline(p)
    loaded_by_id = {c.mutant_id: c for c in loaded}
    assert loaded_by_id["a"].classification == "equivalent"
    assert loaded_by_id["a"].rule_id == "typing-cast-string-noop"


def test_load_baseline_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_baseline(tmp_path / "nope.json") == []


def test_detect_exclusion_growth_warns_when_set_grows() -> None:
    prev = classify_survivors(
        [MutantDescriptor(mutant_id="a", source_line='cast("T", v)', context="")]
    )
    new = classify_survivors(
        [
            MutantDescriptor(mutant_id="a", source_line='cast("T", v)', context=""),
            MutantDescriptor(mutant_id="c", source_line='cast("U", v)', context=""),
        ]
    )
    verdict = detect_exclusion_growth(prev, new)
    assert isinstance(verdict, GrowthVerdict)
    assert verdict.grew is True
    assert "c" in verdict.added
    assert verdict.severity in ("warn", "fail")


def test_detect_exclusion_growth_clean_when_no_new_exclusions() -> None:
    prev = classify_survivors(
        [MutantDescriptor(mutant_id="a", source_line='cast("T", v)', context="")]
    )
    # 'a' still excluded; 'b' is pending (NOT excluded) → exclusion set unchanged
    new = classify_survivors(
        [
            MutantDescriptor(mutant_id="a", source_line='cast("T", v)', context=""),
            MutantDescriptor(mutant_id="b", source_line="x - y", context=""),
        ]
    )
    verdict = detect_exclusion_growth(prev, new)
    assert verdict.grew is False
    assert verdict.added == ()
    assert verdict.severity == "ok"


def test_growth_guard_blocks_relabel_loophole() -> None:
    # Relabeling a previously-pending survivor as excluded MUST be caught.
    prev = classify_survivors(
        [MutantDescriptor(mutant_id="a", source_line="x - y", context="")]
    )  # a was pending → not excluded
    new = classify_survivors(
        [MutantDescriptor(mutant_id="a", source_line='cast("T", v)', context="")]
    )  # a now excluded
    verdict = detect_exclusion_growth(prev, new)
    assert verdict.grew is True
    assert "a" in verdict.added


def test_cli_classify_reports_score_and_growth(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import harness_maker.spec_mutation as sm

    survivors_doc = {
        "killed": 80,
        "survivors": [
            {"mutant_id": "eq1", "source_line": 'cast("T", v)', "context": ""},
            {"mutant_id": "p1", "source_line": "a - b", "context": ""},
        ],
    }
    inp = tmp_path / "survivors.json"
    inp.write_text(json.dumps(survivors_doc))
    out = tmp_path / "baseline.json"
    rc = sm.main(["classify", "--input", str(inp), "--baseline-out", str(out)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "excluded" in text.lower()
    # baseline persisted with both mutants
    data = json.loads(out.read_text())
    assert {e["mutant_id"] for e in data["classifications"]} == {"eq1", "p1"}


def test_cli_classify_growth_warns_against_prior_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import harness_maker.spec_mutation as sm

    prior = baseline_to_json(
        classify_survivors(
            [MutantDescriptor(mutant_id="a", source_line='cast("T", v)', context="")]
        )
    )
    prev_path = tmp_path / "prev.json"
    prev_path.write_text(prior)

    survivors_doc = {
        "killed": 90,
        "survivors": [
            {"mutant_id": "a", "source_line": 'cast("T", v)', "context": ""},
            {"mutant_id": "c", "source_line": 'cast("U", v)', "context": ""},
        ],
    }
    inp = tmp_path / "survivors.json"
    inp.write_text(json.dumps(survivors_doc))
    rc = sm.main(["classify", "--input", str(inp), "--prev-baseline", str(prev_path)])
    # growth is warn-level → non-zero advisory but documented; assert it surfaces
    out = capsys.readouterr().out
    assert "growth" in out.lower() or "grew" in out.lower()
    assert rc in (0, 3)
