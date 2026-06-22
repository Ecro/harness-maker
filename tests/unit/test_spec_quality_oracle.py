"""Phase 3 — spec_quality oracle_independence dimension (ADR-003/007, C2/C9).

Scores oracle EVIDENCE quality (not the declared enum label), blocks in
spec-driven mode, and treats a durable waiver as an auditable task-driven
override. Only scored for schema_version >= 2 specs.
"""

from __future__ import annotations

import yaml

from harness_maker.spec_quality import evaluate_spec

_SPEC_TEXT = (
    "# Intent\nDo the thing.\n## Scenarios\n**Given** x **When** y **Then** z\n"
    "## Verification Criteria\n| S1 | unit | test_s1 |\n## Non-Goals\nout-of-scope: nothing\n"
)


def _machine(
    *, oracle_source: str, evidence: str, waiver: str | None = None, version: int = 2
) -> str:
    ac = {
        "id": "AC-001",
        "title": "t",
        "type": "mechanical",
        "pending_test": True,
        "executable_predicate": "x == 1",
        "oracle_source": oracle_source,
        "oracle_evidence": evidence,
    }
    if waiver is not None:
        ac["oracle_independence_waiver"] = waiver
    return yaml.safe_dump(
        {
            "schema_version": version,
            "spec_slug": "x",
            "verification_tier": 1,
            "mutation_threshold": 85,
            "paths_to_mutate": ["src/harness_maker/x.py"],
            "ac": [ac],
        }
    )


def test_evidence_less_high_label_oracle_scores_low() -> None:
    """Declaring a high-scoring source with NO evidence must not pass — C2 anti-gaming."""
    m = _machine(oracle_source="golden", evidence="")
    result = evaluate_spec(_SPEC_TEXT, "task-driven", machine_yaml=m)
    assert "oracle_independence" in result.scores
    assert result.scores["oracle_independence"] < 40


def test_evidence_less_oracle_blocks_in_spec_driven() -> None:
    m = _machine(oracle_source="golden", evidence="")
    result = evaluate_spec(_SPEC_TEXT, "spec-driven", machine_yaml=m)
    assert result.blocked is True
    assert "oracle_independence" in result.weak_dimensions


def test_evidence_less_oracle_warns_not_blocks_in_task_driven() -> None:
    m = _machine(oracle_source="golden", evidence="")
    result = evaluate_spec(_SPEC_TEXT, "task-driven", machine_yaml=m)
    assert result.blocked is False
    assert "oracle_independence" in result.weak_dimensions


def test_specific_evidence_scores_high() -> None:
    m = _machine(
        oracle_source="differential",
        evidence="compared against the reference implementation golden bytes in tests/golden/",
    )
    result = evaluate_spec(_SPEC_TEXT, "spec-driven", machine_yaml=m)
    assert result.scores["oracle_independence"] >= 60
    assert "oracle_independence" not in result.weak_dimensions


def test_durable_waiver_lifts_task_driven_low_independence() -> None:
    m = _machine(
        oracle_source="golden",
        evidence="",
        waiver="accepted: prototype, oracle hardening deferred to v2 of this feature",
    )
    result = evaluate_spec(_SPEC_TEXT, "task-driven", machine_yaml=m)
    assert result.scores["oracle_independence"] >= 60


def test_v1_spec_omits_oracle_independence_dim() -> None:
    """Pre-v2 specs are surfaced advisory by spec_drift, not scored/blocked here (ADR-006)."""
    m = _machine(oracle_source="legacy-unspecified", evidence="", version=1)
    result = evaluate_spec(_SPEC_TEXT, "spec-driven", machine_yaml=m)
    assert "oracle_independence" not in result.scores


def test_waiver_does_not_bypass_spec_driven_gate() -> None:
    """REVIEW Codex-M: a waiver is task-driven-only; spec-driven blocks regardless."""
    m = _machine(
        oracle_source="golden",
        evidence="",  # low evidence
        waiver="accepted: prototype",
    )
    result = evaluate_spec(_SPEC_TEXT, "spec-driven", machine_yaml=m)
    # The waiver must NOT lift the score in spec-driven mode → still weak + blocked.
    assert result.scores["oracle_independence"] < 40
    assert result.blocked is True


def test_nonnumeric_schema_version_degrades_not_crash() -> None:
    """REVIEW C-P1: a hand-authored non-numeric schema_version must degrade to v1, not crash."""
    bad = yaml.safe_dump(
        {
            "schema_version": "two",
            "spec_slug": "x",
            "verification_tier": 1,
            "ac": [{"id": "AC-001", "title": "t", "type": "mechanical", "pending_test": True}],
        }
    )
    # Must not raise; treated as v1 → oracle_independence dim omitted.
    result = evaluate_spec(_SPEC_TEXT, "spec-driven", machine_yaml=bad)
    assert "oracle_independence" not in result.scores
