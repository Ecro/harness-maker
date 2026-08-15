"""Tests for spec_mutation (P1, ADR-005)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
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
    _parse_mutmut_output,
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

    # A fully-absent mutmut raises FNF on BOTH the `--version` precheck and the
    # `mutmut run` call (same missing binary) — the realistic model. The precheck
    # catches FNF and falls through, so the existing absent contract is preserved.
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


def _fake_run_factory(
    version_out: str, *, on_run: Callable[..., Any], version_rc: int = 0
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Command-discriminating ``subprocess.run`` replacement (PLAN-mutmut-3x-pin).

    ``mutmut --version`` returns a CompletedProcess carrying ``version_out`` (and
    exit ``version_rc``, default 0); the ``mutmut run …`` invocation delegates to
    ``on_run`` (which returns a CompletedProcess or raises). This isolates the
    version-precheck from the mutation-run behavior so a test no longer
    accidentally couples the two.
    """

    def _fake(cmd: list[str], *a: Any, **kw: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["mutmut", "--version"]:
            return subprocess.CompletedProcess(cmd, version_rc, stdout=version_out, stderr="")
        return on_run(cmd, *a, **kw)

    return _fake


def test_measure_baseline_timeout_preserves_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TimeoutExpired on ``mutmut run`` keeps partial stdout/stderr (REVIEW C-P1-E).

    Without this, a long mutmut run that completes 200/250 mutants returns a
    0% score after timeout — spuriously failing the gate. The version precheck
    succeeds (2.x) so only the run call times out, isolating this behavior.
    """
    import harness_maker.spec_mutation as sm

    def _run_timeout(_cmd: list[str], *_a: Any, **_kw: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            cmd=["mutmut"],
            timeout=10,
            output=b"killed: 80\nsurvived: 20\n",
            stderr=b"",
        )

    monkeypatch.setattr(
        sm.subprocess, "run", _fake_run_factory("mutmut 2.5.1", on_run=_run_timeout)
    )

    rep = measure_baseline(["src/x.py"], cwd=tmp_path, timeout_seconds=10)
    # Partial output must be parsed — not zeroed.
    assert rep.killed == 80
    assert rep.survived == 20
    assert rep.score == pytest.approx(0.80)


def test_measure_baseline_mutmut_3x_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mutmut 3.x detected → unsupported sentinel report; ``mutmut run`` is NEVER invoked.

    The 2.x CLI (`--paths-to-mutate`) is incompatible with 3.x; the guard must
    short-circuit before the run call rather than let it spuriously FAIL.
    """
    import harness_maker.spec_mutation as sm

    def _run_must_not_run(cmd: list[str], *_a: Any, **_kw: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"mutmut run must not be invoked when 3.x is detected: {cmd}")

    monkeypatch.setattr(
        sm.subprocess, "run", _fake_run_factory("mutmut 3.0.0", on_run=_run_must_not_run)
    )

    rep = measure_baseline(["src/x.py"], cwd=tmp_path, timeout_seconds=5)
    assert sm._MUTMUT_UNSUPPORTED in rep.raw_output
    assert rep.killed == 0
    assert rep.survived == 0
    assert rep.total == 0
    assert rep.paths == ("src/x.py",)


def test_measure_baseline_unparsable_version_proceeds_as_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unparsable ``mutmut --version`` → treat as supported and reach the run path.

    Ambiguity must never false-skip a working 2.x install.
    """
    import harness_maker.spec_mutation as sm

    def _run_counts(_cmd: list[str], *_a: Any, **_kw: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(_cmd, 0, stdout="killed: 7\nsurvived: 3\n", stderr="")

    monkeypatch.setattr(
        sm.subprocess, "run", _fake_run_factory("garbage with no version", on_run=_run_counts)
    )

    rep = measure_baseline(["src/x.py"], cwd=tmp_path, timeout_seconds=5)
    assert sm._MUTMUT_UNSUPPORTED not in rep.raw_output
    assert rep.killed == 7
    assert rep.survived == 3


def test_measure_baseline_version_nonzero_exit_proceeds_as_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-zero `mutmut --version` exit is ambiguous → fall through, never skip.

    Guards against a broken install whose failing `--version` spews version-shaped
    text (here a stray '3.0.0') being misread as unsupported (REVIEW Codex P2).
    """
    import harness_maker.spec_mutation as sm

    def _run_counts(_cmd: list[str], *_a: Any, **_kw: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(_cmd, 0, stdout="killed: 5\nsurvived: 1\n", stderr="")

    monkeypatch.setattr(
        sm.subprocess,
        "run",
        _fake_run_factory("Traceback ... mutmut 3.0.0", on_run=_run_counts, version_rc=1),
    )

    rep = measure_baseline(["src/x.py"], cwd=tmp_path, timeout_seconds=5)
    assert sm._MUTMUT_UNSUPPORTED not in rep.raw_output
    assert rep.killed == 5


def test_measure_baseline_2x_minor_not_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 2.x minor (2.10.3) must NOT be classified unsupported — locks the >=3 boundary."""
    import harness_maker.spec_mutation as sm

    def _run_counts(_cmd: list[str], *_a: Any, **_kw: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(_cmd, 0, stdout="killed: 9\nsurvived: 1\n", stderr="")

    monkeypatch.setattr(
        sm.subprocess, "run", _fake_run_factory("mutmut version 2.10.3", on_run=_run_counts)
    )

    rep = measure_baseline(["src/x.py"], cwd=tmp_path, timeout_seconds=5)
    assert sm._MUTMUT_UNSUPPORTED not in rep.raw_output
    assert rep.killed == 9


def test_measure_baseline_future_major_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A future major (4.0.0) is also unsupported — the 2.x CLI stays incompatible."""
    import harness_maker.spec_mutation as sm

    def _run_must_not_run(cmd: list[str], *_a: Any, **_kw: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"mutmut run must not be invoked for an unsupported major: {cmd}")

    monkeypatch.setattr(
        sm.subprocess, "run", _fake_run_factory("mutmut 4.0.0", on_run=_run_must_not_run)
    )

    rep = measure_baseline(["src/x.py"], cwd=tmp_path, timeout_seconds=5)
    assert sm._MUTMUT_UNSUPPORTED in rep.raw_output
    assert rep.total == 0


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


def _report(
    killed: int, survived: int, *, raw: str = "", tool_missing: bool = False
) -> MutationReport:
    return MutationReport(
        paths=("src/x.py",),
        killed=killed,
        survived=survived,
        timeout=0,
        suspicious=0,
        skipped=0,
        sampled=False,
        raw_output=raw or f"killed: {killed} survived: {survived}",
        tool_missing=tool_missing,
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
    """mutmut not installed → non-gating (exit 0) with a skip notice.

    Updated by the round-1 review: the skip now keys on `tool_missing`, set only where absence
    is observed (the `FileNotFoundError` branch), not on a substring of the captured output.
    The sibling test below is the reason.
    """
    import harness_maker.spec_mutation as sm

    yp = _write_machine(tmp_path, paths=["src/x.py"])
    monkeypatch.setattr(
        sm,
        "measure_baseline",
        lambda *a, **k: _report(0, 0, raw="mutmut: command not found", tool_missing=True),
    )
    rc = sm.main(["gate", "--yaml", str(yp), "--tier", "1"])
    assert rc == 0
    assert "not installed" in capsys.readouterr().err


def test_cli_gate_loud_skips_when_mutmut_3x(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """mutmut 3.x → non-gating (exit 0) with an unsupported notice, not a spurious FAIL."""
    import harness_maker.spec_mutation as sm

    yp = _write_machine(tmp_path, paths=["src/x.py"])
    monkeypatch.setattr(
        sm,
        "measure_baseline",
        lambda *a, **k: _report(0, 0, raw=f"{sm._MUTMUT_UNSUPPORTED} 3.0.0"),
    )
    rc = sm.main(["gate", "--yaml", str(yp), "--tier", "1"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "unsupported" in err.lower()


def test_cli_gate_absent_when_version_precheck_fnf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """mutmut absent (FNF on the `--version` precheck) → absent-skip (exit 0).

    Regression guard (PLAN-mutmut-3x-pin W1): the new version precheck must NOT
    turn the genuinely-absent case into the unsupported notice or a spurious
    FAIL. Uses the REAL measure_baseline so the precheck FNF → fall-through →
    run-FNF → absent path is exercised end-to-end.
    """
    import harness_maker.spec_mutation as sm

    def _raise_fnf(*_a: Any, **_kw: Any) -> None:
        raise FileNotFoundError("mutmut: not installed (mocked)")

    monkeypatch.setattr(sm.subprocess, "run", _raise_fnf)
    yp = _write_machine(tmp_path, paths=["src/x.py"])
    rc = sm.main(["gate", "--yaml", str(yp), "--tier", "1"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "not installed" in err  # absent notice
    assert "unsupported" not in err.lower()  # NOT the 3.x notice


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


# ── F5: the three faults that made the tier-1 gate unpassable for every SPEC ──
#
# All three were live simultaneously and each masked the next. Diagnosed 2026-08-15 against
# mutmut 2.5; every number below is measured, not constructed.

#: A verbatim tail of a real `mutmut run` on `src/harness_maker/lens_coverage.py`, scoped to
#: `tests/unit/test_lens_coverage.py`. 55 mutants: 42 killed, 13 survived. Kept as a literal
#: rather than a hand-written approximation, because the fault was that the wrapper could not
#: read THIS format — a paraphrase would have been readable and would have tested nothing.
_REAL_MUTMUT_TAIL = (
    "Legend for output:\n"
    "\N{PARTY POPPER} Killed mutants.   The goal is for everything to end up in this bucket.\n"
    "\N{ALARM CLOCK} Timeout.          Test suite took 10 times as long as the baseline.\n"
    "\N{THINKING FACE} Suspicious.       Tests took a long time, but not long enough.\n"
    "\N{SLIGHTLY FROWNING FACE} Survived.         This means your tests need to be expanded.\n"
    "\N{SPEAKER WITH CANCELLATION STROKE} Skipped.          Skipped.\n"
    "\n2. Checking mutants\n"
    "\r\N{BRAILLE PATTERN DOTS-24} 12/55  \N{PARTY POPPER} 9  \N{ALARM CLOCK} 0  "
    "\N{THINKING FACE} 0  \N{SLIGHTLY FROWNING FACE} 3  "
    "\N{SPEAKER WITH CANCELLATION STROKE} 0"
    "\r\N{BRAILLE PATTERN DOTS-24} 55/55  \N{PARTY POPPER} 42  \N{ALARM CLOCK} 0  "
    "\N{THINKING FACE} 0  \N{SLIGHTLY FROWNING FACE} 13  "
    "\N{SPEAKER WITH CANCELLATION STROKE} 0"
)


def test_fault1_the_emoji_progress_line_is_parsed() -> None:
    """mutmut 2.x never writes the words `killed:`/`survived:` — only the legend's emoji.

    The old `_COUNTERS_RE` scanned for the English words, so a healthy 42/13 run parsed as
    all-zeros and the gate reported `score 0%`. That is what every tier-1 SPEC in this repo has
    been showing.
    """
    report = _parse_mutmut_output(
        _REAL_MUTMUT_TAIL, ("src/harness_maker/lens_coverage.py",), sampled=False
    )
    assert (report.killed, report.survived) == (42, 13)
    assert report.timeout == report.suspicious == report.skipped == 0
    assert round(report.score * 100) == 76


def test_fault1_the_last_progress_line_wins_not_the_first() -> None:
    """The line is rewritten in place with `\\r`; an early frame is progress, not a result.

    Taking the first match would have reported 9/3 (16 mutants in) as the final tally — a
    plausible-looking number that is simply the wrong moment.
    """
    report = _parse_mutmut_output(_REAL_MUTMUT_TAIL, ("x",), sampled=False)
    assert report.killed != 9, "an intermediate progress frame was read as the final count"
    assert report.killed == 42


def test_fault3_a_zero_report_is_not_a_score_of_zero() -> None:
    """The collision that hid the other two faults for the lifetime of the gate.

    A crashed runner, a timeout, and an unparseable format all produce an all-zero report, and
    `score` returns 0.0 for it only because the denominator is empty. Reported as `score 0% <
    threshold 85%` it is indistinguishable from "every mutant survived" — so three broken runs
    read as a legitimate measurement of weak tests.
    """
    crashed = _parse_mutmut_output(
        "# mutmut timeout after 600s; consider sampled=True", ("x",), sampled=False
    )
    assert not crashed.ran
    passes, reason = gate(crashed, 1)
    assert not passes
    assert "ZERO mutants" in reason
    assert "score 0%" not in reason, (
        "the broken-run branch still reports a score, which is the collision it exists to break"
    )


def test_fault3_a_real_wipeout_still_reports_a_score() -> None:
    """The counterpart: 0 killed with mutants CHECKED is a genuine measurement, not a crash."""
    wipeout = _parse_mutmut_output(
        "\N{PARTY POPPER} 0  \N{ALARM CLOCK} 0  \N{THINKING FACE} 0  "
        "\N{SLIGHTLY FROWNING FACE} 55  \N{SPEAKER WITH CANCELLATION STROKE} 0",
        ("x",),
        sampled=False,
    )
    assert wipeout.ran
    passes, reason = gate(wipeout, 1)
    assert not passes
    assert "score 0%" in reason, "a true wipeout must still be reported as a score"


def test_fault2_the_runner_is_passed_through_to_mutmut(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without `--runner`, mutmut runs the WHOLE suite per mutant.

    In this repo that is ~6 min, so the first mutant exhausts the 600 s cap and the run yields
    the all-zero report of fault 3. The flag is not a speed knob — it is what makes a
    measurement possible at all.
    """
    seen: dict[str, list[str]] = {}

    def _fake_run(args: list[str], **kwargs: Any) -> Any:
        seen["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout=_REAL_MUTMUT_TAIL, stderr="")

    monkeypatch.setattr("harness_maker.spec_mutation._detect_unsupported_mutmut", lambda cwd: None)
    monkeypatch.setattr(subprocess, "run", _fake_run)

    measure_baseline(["src/x.py"], cwd=Path("."), runner="python -m pytest -q tests/unit/test_x.py")
    assert "--runner" in seen["args"]
    assert (
        seen["args"][seen["args"].index("--runner") + 1]
        == "python -m pytest -q tests/unit/test_x.py"
    )

    seen.clear()
    measure_baseline(["src/x.py"], cwd=Path("."))
    assert "--runner" not in seen["args"], "a runner was invented when the caller passed none"


def test_fault4_a_truncated_run_is_not_a_score_either() -> None:
    """A fault the emoji fix CREATED, caught by re-reading the timeout branch after landing it.

    The timeout handler deliberately preserves partial stdout (REVIEW C-P1-E). Before the emoji
    parser that partial output parsed to all-zeros, so a truncated run was indistinguishable
    from a non-run — bad, but at least it did not lie about a number. With the parser working,
    the same partial output yields a real-looking score that the gate would have reported as
    the result for the whole path set.

    Measured: the four-file gate run reported 46%, and the wall budget is 600 s for four files.
    Whether that 46% was complete or a prefix could not be told apart from the output, which is
    exactly the collision `ran` exists to break, one level up.
    """
    partial = _parse_mutmut_output(
        "\N{PARTY POPPER} 12  \N{ALARM CLOCK} 0  \N{THINKING FACE} 0  "
        "\N{SLIGHTLY FROWNING FACE} 14  \N{SPEAKER WITH CANCELLATION STROKE} 0"
        "\n# mutmut timeout after 600s; consider sampled=True",
        ("a.py", "b.py"),
        sampled=False,
        truncated=True,
    )
    assert partial.ran, "the prefix DID check mutants — this is not the non-run case"
    passes, reason = gate(partial, 1)
    assert not passes
    assert "partial run" in reason
    assert "26 mutant" in reason, "the operator needs to know how far it got"
    assert "%" not in reason, "a prefix must not be reported as a percentage of the whole path set"


def test_fault4_a_complete_run_is_not_flagged_as_partial() -> None:
    """The counterpart — the guard must not make every real measurement unreportable."""
    complete = _parse_mutmut_output(
        "\N{PARTY POPPER} 42  \N{ALARM CLOCK} 0  \N{THINKING FACE} 0  "
        "\N{SLIGHTLY FROWNING FACE} 13  \N{SPEAKER WITH CANCELLATION STROKE} 0",
        ("x.py",),
        sampled=False,
    )
    assert not complete.truncated
    passes, reason = gate(complete, 1)
    assert not passes  # 76% < 85%
    assert "score 76%" in reason


def test_fault4_the_timeout_path_marks_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """The flag must be set where the truncation happens, not inferred by a caller."""

    def _timeout(args: list[str], **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(
            cmd=args,
            timeout=600,
            output="\N{PARTY POPPER} 5  \N{SLIGHTLY FROWNING FACE} 1",
        )

    monkeypatch.setattr("harness_maker.spec_mutation._detect_unsupported_mutmut", lambda cwd: None)
    monkeypatch.setattr(subprocess, "run", _timeout)
    report = measure_baseline(["src/x.py"], cwd=Path("."))
    assert report.truncated, "a wall-budget timeout produced a report that claims to be complete"


def test_a_runner_saying_command_not_found_does_not_look_like_absent_mutmut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Round-1 review P1. The skip was a substring test against arbitrary subprocess output.

    `--runner` injects a user-supplied test command that mutmut executes per mutant, and its
    stderr flows into the captured blob. A runner naming a binary absent from PATH put
    `pytest: command not found` there — so a mutmut that was present, running, and failing
    every mutant made the gate exit 0 announcing mutmut was not installed. `report.ran`,
    `truncated` and the score were never consulted, because the substring check preceded them.

    The same *no-observation-reported-as-an-observation* class the module docstring exists to
    end, one layer up from where it was fixed.
    """
    import harness_maker.spec_mutation as sm

    yp = _write_machine(tmp_path, paths=["src/x.py"])
    monkeypatch.setattr(
        sm,
        "measure_baseline",
        lambda *a, **k: _report(0, 0, raw="pytest: command not found\n", tool_missing=False),
    )
    rc = sm.main(["gate", "--yaml", str(yp), "--tier", "1"])
    assert rc == 1, "a broken run was reported as an absent tool"
    err = capsys.readouterr().err
    assert "not installed" not in err
    assert "ZERO mutants" in err
