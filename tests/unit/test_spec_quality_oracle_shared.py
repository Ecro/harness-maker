"""Phase 2 — spec_quality imports the shared scorer; value-matrix + static dup-guard.

PLAN-wrapup-waiver-enforcement ADR-001 / validation C4/C7. The aggregate
oracle_independence dim must agree with spec_machine.score_ac_oracle_evidence
on the full value matrix, and the evidence markers/threshold must live in
exactly ONE module (no silent drift re-introduction).
"""

from __future__ import annotations

import yaml

from harness_maker import spec_quality
from harness_maker.spec_quality import evaluate_spec

_SPEC_TEXT = (
    "# Intent\nDo the thing.\n## Scenarios\n**Given** x **When** y **Then** z\n"
    "## Verification Criteria\n| S1 | unit | test_s1 |\n## Non-Goals\nout-of-scope: nothing\n"
)


def _dim(ac: dict, dev_mode: str = "task-driven") -> int:
    m = yaml.safe_dump(
        {
            "schema_version": 2,
            "spec_slug": "x",
            "verification_tier": 1,
            "mutation_threshold": 85,
            "paths_to_mutate": ["src/harness_maker/x.py"],
            "ac": [ac],
        }
    )
    return evaluate_spec(_SPEC_TEXT, dev_mode, machine_yaml=m).scores["oracle_independence"]


def test_value_matrix_single_ac() -> None:
    base = {"id": "AC-001", "title": "t", "oracle_source": "golden"}
    # legacy-unspecified → denominator-retained 0 (single AC → dim 0)
    assert _dim({"id": "AC-001", "title": "t", "oracle_source": "legacy-unspecified"}) == 0
    assert _dim({**base, "oracle_evidence": ""}) == 20  # empty
    assert _dim({**base, "oracle_evidence": "short"}) == 40  # <15 chars
    assert _dim({**base, "oracle_evidence": "see reference golden /x"}) == 85  # marker
    assert _dim({**base, "oracle_evidence": "a fairly generic justification line"}) == 60  # generic


def test_value_matrix_waiver_and_mode() -> None:
    weak_waived = {
        "id": "AC-001",
        "title": "t",
        "oracle_source": "golden",
        "oracle_evidence": "",
        "oracle_independence_waiver": "accepted: prototype",
    }
    # task-driven: waiver lifts to 100
    assert _dim(weak_waived, "task-driven") == 100
    # spec-driven: waiver IGNORED → raw evidence score (empty → 20)
    assert _dim(weak_waived, "spec-driven") == 20


def test_value_matrix_legacy_retained_in_denominator() -> None:
    # one legacy (0) + one strong (85) → average 42 (legacy stays in denominator)
    m = yaml.safe_dump(
        {
            "schema_version": 2,
            "spec_slug": "x",
            "verification_tier": 1,
            "ac": [
                {"id": "AC-001", "title": "t", "oracle_source": "legacy-unspecified"},
                {
                    "id": "AC-002",
                    "title": "u",
                    "oracle_source": "differential",
                    "oracle_evidence": "reference impl golden",
                },
            ],
        }
    )
    # round((0 + 85) / 2) == 42 — NOT 85 (legacy is not skipped)
    assert (
        evaluate_spec(_SPEC_TEXT, "task-driven", machine_yaml=m).scores["oracle_independence"] == 42
    )


def test_empty_ac_list_scores_100() -> None:
    m = yaml.safe_dump({"schema_version": 2, "spec_slug": "x", "verification_tier": 1, "ac": []})
    assert (
        evaluate_spec(_SPEC_TEXT, "task-driven", machine_yaml=m).scores["oracle_independence"]
        == 100
    )


# --- static dup-guard (producer-gate, cf. test_owned_uuids_render_gate) -----


def test_markers_and_threshold_live_in_exactly_one_module() -> None:
    """The ladder constants must NOT be re-introduced into spec_quality (ADR-001/C7)."""
    assert not hasattr(spec_quality, "_ORACLE_EVIDENCE_SPECIFICITY_MARKERS")
    assert not hasattr(spec_quality, "ORACLE_EVIDENCE_SPECIFICITY_MARKERS")
    assert not hasattr(spec_quality, "ORACLE_EVIDENCE_WEAK_THRESHOLD")
    # And the shared scorer is imported (not redefined locally).
    assert spec_quality.score_ac_oracle_evidence.__module__ == "harness_maker.spec_machine"
