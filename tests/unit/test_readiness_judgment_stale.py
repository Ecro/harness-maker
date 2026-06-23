"""Tests for the judgment-verdict-freshness advisory signal in /hm:health.

PLAN-judgment-stale-health-display:
- ADR-001: weight=0 AND hard_gate=False — display-only, never docks the
  structural score (the find-unjudged Production gate is the teeth).
- ADR-002: a malformed machine SPEC is fail-LOUD (failed signal naming the
  spec), NOT N-A — present-but-unreadable = freshness unknown.
- Absent-case (no machine SPEC / zero judgment ACs) emits NO signal (N-A).
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import Preset
from harness_maker.readiness import _dim_guardrails, compute_readiness
from harness_maker.spec_machine import mark_judged

_SIG = "judgment_verdict_freshness"


def _signal_of(project_dir: Path, sig_id: str = _SIG):  # type: ignore[no-untyped-def]
    dim = _dim_guardrails(project_dir)
    return next((s for s in dim.signals if s.id == sig_id), None)


def _write_spec(
    project_dir: Path,
    *,
    slug: str = "demo",
    ac_id: str = "AC-001",
    subject_rel: str = "subject.py",
    subject_body: str = "def f():\n    return 1\n",
) -> Path:
    """Write project_dir/specs/SPEC-<slug>.machine.yaml + its subject file."""
    specs = project_dir / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (project_dir / subject_rel).parent.mkdir(parents=True, exist_ok=True)
    (project_dir / subject_rel).write_text(subject_body, encoding="utf-8")
    ac = {
        "id": ac_id,
        "title": "subject is correct",
        "type": "judgment",
        "rubric_id": "skill",
        "oracle_source": "rubric",
        "oracle_evidence": "independent reviewer",
        "judgment_subject_paths": [subject_rel],
    }
    import yaml  # local import keeps the module dependency surface minimal

    data = {"schema_version": 2, "spec_slug": slug, "verification_tier": 1, "ac": [ac]}
    yp = specs / f"SPEC-{slug}.machine.yaml"
    yp.write_text(yaml.safe_dump(data), encoding="utf-8")
    return yp


def _record_pass(project_dir: Path, yp: Path, ac_id: str = "AC-001") -> None:
    errors = mark_judged(yp, ac_id, "pass", "criterion-1: ok (rubric)", cwd=project_dir)
    assert errors == [], errors


# (a) stale → failed signal listing the EXACT pinned id "SPEC-<slug>:<ac>"
def test_stale_verdict_fails_signal_with_pinned_id(tmp_path: Path) -> None:
    yp = _write_spec(tmp_path)
    _record_pass(tmp_path, yp)
    # drift the subject → the recorded hash no longer matches
    (tmp_path / "subject.py").write_text("def f():\n    return 2  # drifted\n", encoding="utf-8")

    sig = _signal_of(tmp_path)
    assert sig is not None
    assert sig.passed is False
    assert "SPEC-demo:AC-001" in sig.evidence  # exact pinned id form (ADR/W3)
    assert sig.action is not None


# (b) all-fresh → passing signal whose evidence carries the fresh count K
def test_all_fresh_passes_signal_with_count(tmp_path: Path) -> None:
    yp = _write_spec(tmp_path)
    _record_pass(tmp_path, yp)

    sig = _signal_of(tmp_path)
    assert sig is not None
    assert sig.passed is True
    assert "1 judgment verdict(s) fresh" in sig.evidence


# (c1) no machine SPEC → N-A (no signal emitted at all)
def test_no_machine_spec_emits_no_signal(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    assert _signal_of(tmp_path) is None
    # also: a specs/ dir with no SPEC-*.machine.yaml file
    (tmp_path / "specs").mkdir()
    assert _signal_of(tmp_path) is None


# (c2) machine SPEC present but ZERO judgment ACs → N-A (no signal)
def test_machine_spec_zero_judgment_acs_emits_no_signal(tmp_path: Path) -> None:
    import yaml

    specs = tmp_path / "specs"
    specs.mkdir(parents=True)
    data = {
        "schema_version": 2,
        "spec_slug": "mech",
        "verification_tier": 1,
        "ac": [
            {"id": "AC-001", "title": "m", "type": "mechanical", "executable_predicate": "f() == 1"}
        ],
    }
    (specs / "SPEC-mech.machine.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    assert _signal_of(tmp_path) is None


# (d) malformed machine.yaml → failed signal naming the spec, NO crash (ADR-002 fail-loud)
def test_malformed_machine_yaml_fails_signal_no_crash(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir(parents=True)
    (specs / "SPEC-bad.machine.yaml").write_text("{ this is : not valid : yaml [", encoding="utf-8")

    sig = _signal_of(tmp_path)  # must not raise
    assert sig is not None
    assert sig.passed is False
    assert "SPEC-bad" in sig.evidence
    assert "malformed" in sig.evidence.lower()


# (d2) partial: one SPEC stale + one SPEC malformed → ONE failed signal reporting BOTH
def test_partial_stale_and_malformed_reports_both(tmp_path: Path) -> None:
    yp = _write_spec(tmp_path, slug="good", subject_rel="good_subj.py")
    _record_pass(tmp_path, yp)
    (tmp_path / "good_subj.py").write_text("# drifted\n", encoding="utf-8")  # stale
    (tmp_path / "specs" / "SPEC-bad.machine.yaml").write_text("{ broken [", encoding="utf-8")

    sig = _signal_of(tmp_path)
    assert sig is not None
    assert sig.passed is False
    assert "SPEC-good:AC-001" in sig.evidence  # the stale id
    assert "SPEC-bad" in sig.evidence  # the malformed spec


# (e) score-invariance, fresh-vs-stale SAME fixture (not stale-vs-absent):
#     weight==0 AND hard_gate is False AND guardrails score AND composite unchanged.
def test_signal_weight_zero_hard_gate_false_score_and_composite_invariant(tmp_path: Path) -> None:
    yp = _write_spec(tmp_path)
    _record_pass(tmp_path, yp)

    # arm 1 — fresh
    fresh_sig = _signal_of(tmp_path)
    assert fresh_sig is not None
    assert fresh_sig.passed is True
    fresh_dim = _dim_guardrails(tmp_path).score
    fresh_composite = compute_readiness(tmp_path, Preset.PRODUCTION).composite

    # arm 2 — same fixture, subject drifted (signal now present-and-FAILING)
    (tmp_path / "subject.py").write_text("def f():\n    return 99\n", encoding="utf-8")
    stale_sig = _signal_of(tmp_path)
    assert stale_sig is not None
    assert stale_sig.passed is False
    stale_dim = _dim_guardrails(tmp_path).score
    stale_composite = compute_readiness(tmp_path, Preset.PRODUCTION).composite

    # the advisory is genuinely display-only
    assert fresh_sig.weight == 0
    assert fresh_sig.hard_gate is False
    assert stale_sig.weight == 0
    assert stale_sig.hard_gate is False
    # a weight>0 OR hard_gate=True regression would make these differ
    assert fresh_dim == stale_dim
    assert fresh_composite == stale_composite
    # stronger: the signal contributes EXACTLY 0 — equal to the score with no signal
    # at all (a project with no specs/ never emits judgment_verdict_freshness).
    no_signal_dir = tmp_path / "bare"
    no_signal_dir.mkdir()
    assert _signal_of(no_signal_dir) is None
    assert fresh_dim == _dim_guardrails(no_signal_dir).score


# REVIEW F2a (most-valuable missing test): cross-SPEC count aggregation (N>1).
def test_two_fresh_specs_count_aggregation(tmp_path: Path) -> None:
    yp_a = _write_spec(tmp_path, slug="aaa", subject_rel="a_subj.py")
    _record_pass(tmp_path, yp_a)
    yp_b = _write_spec(tmp_path, slug="bbb", subject_rel="b_subj.py")
    _record_pass(tmp_path, yp_b)

    sig = _signal_of(tmp_path)
    assert sig is not None
    assert sig.passed is True
    assert "2 judgment verdict(s) fresh across 2 SPEC(s)" in sig.evidence


# REVIEW F2b: a judgment AC with a null (unjudged) verdict → signal present, PASSING,
# "0 fresh" (the find-unjudged gate owns unjudged ACs; freshness only tracks passes).
def test_null_verdict_ac_emits_passing_zero_fresh(tmp_path: Path) -> None:
    _write_spec(tmp_path)  # no _record_pass → verdict stays null

    sig = _signal_of(tmp_path)
    assert sig is not None
    assert sig.passed is True
    assert "0 judgment verdict(s) fresh" in sig.evidence


# REVIEW F1 (R1+R2 consensus): a pass verdict whose subject is fully ABSENT on disk is
# out-of-scope (detector skips it) → must NOT be counted toward the "N fresh" tally.
def test_absent_subject_pass_not_counted_fresh(tmp_path: Path) -> None:
    import yaml

    specs = tmp_path / "specs"
    specs.mkdir(parents=True)
    (tmp_path / "in_scope.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "will_vanish.py").write_text("def g():\n    return 2\n", encoding="utf-8")
    data = {
        "schema_version": 2,
        "spec_slug": "two",
        "verification_tier": 1,
        "ac": [
            {
                "id": "AC-001",
                "title": "in scope",
                "type": "judgment",
                "rubric_id": "skill",
                "oracle_source": "rubric",
                "oracle_evidence": "reviewer",
                "judgment_subject_paths": ["in_scope.py"],
            },
            {
                "id": "AC-002",
                "title": "will be absent",
                "type": "judgment",
                "rubric_id": "skill",
                "oracle_source": "rubric",
                "oracle_evidence": "reviewer",
                "judgment_subject_paths": ["will_vanish.py"],
            },
        ],
    }
    yp = specs / "SPEC-two.machine.yaml"
    yp.write_text(yaml.safe_dump(data), encoding="utf-8")
    # record a pass for BOTH while their subjects exist
    assert mark_judged(yp, "AC-001", "pass", "ok-1", cwd=tmp_path) == []
    assert mark_judged(yp, "AC-002", "pass", "ok-2", cwd=tmp_path) == []
    # now AC-002's subject vanishes → fully absent → out-of-scope (neither fresh nor stale)
    (tmp_path / "will_vanish.py").unlink()

    sig = _signal_of(tmp_path)
    assert sig is not None
    assert sig.passed is True  # AC-001 fresh, AC-002 out-of-scope (not stale)
    # only the in-scope pass counts — NOT 2
    assert "1 judgment verdict(s) fresh" in sig.evidence
