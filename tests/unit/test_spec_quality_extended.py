"""Tests for spec_quality extended dims (P1, ADR-006/009)."""

from __future__ import annotations

import yaml

from harness_maker.spec_quality import (
    RUBRIC_DIMENSIONS,
    evaluate_spec,
)

MINIMAL_GOOD_SPEC = """# SPEC

## Intent
Render the foo with a content_hash.

## In-Scope Scenarios
### S1
Given a feature input, when render runs, then the rendered text includes a content_hash.

## Constraints
| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | project default |

## Verification Criteria
| Scenario | Verification mode | Test name |
|---|---|---|
| S1 | unit | test_render_emits_hash |

## Non-Goals
- nothing
"""


def test_backward_compat_two_arg_signature_still_works() -> None:
    """Existing callsites pass (spec_text, dev_mode) — must not regress (Risk R12)."""
    result = evaluate_spec(MINIMAL_GOOD_SPEC, "task-driven")
    # Result has the original 5 dims.
    for dim in RUBRIC_DIMENSIONS:
        assert dim in result.scores


def test_backward_compat_one_arg_signature_still_works() -> None:
    result = evaluate_spec(MINIMAL_GOOD_SPEC)
    assert result.dev_mode == "task-driven"
    for dim in RUBRIC_DIMENSIONS:
        assert dim in result.scores


def test_machine_yaml_adds_three_dims() -> None:
    machine_yaml = yaml.safe_dump(
        {
            "schema_version": 1,
            "spec_slug": "render",
            "verification_tier": 1,
            "mutation_threshold": 85,
            "paths_to_mutate": ["src/harness_maker/render.py"],
            "ac": [
                {
                    "id": "AC-001",
                    "title": "x",
                    "type": "mechanical",
                    "test_ids": ["t::f"],
                    "executable_predicate": "True",
                }
            ],
        }
    )
    result = evaluate_spec(MINIMAL_GOOD_SPEC, machine_yaml=machine_yaml)
    # The 3 unconditional machine dims are always added. oracle_independence is
    # v2-gated (spec-tetrad ADR-006) and this fixture is schema_version 1, so it
    # is correctly absent here (covered by test_spec_quality_oracle).
    for dim in ("machine_verifiability", "mutation_coverage_set", "non_python_intent_alignment"):
        assert dim in result.scores
    assert "oracle_independence" not in result.scores


def test_machine_verifiability_full_pass() -> None:
    machine_yaml = yaml.safe_dump(
        {
            "spec_slug": "x",
            "verification_tier": 1,
            "ac": [
                {
                    "id": "AC-001",
                    "title": "t",
                    "type": "mechanical",
                    "executable_predicate": "True",
                },
                {
                    "id": "AC-002",
                    "title": "u",
                    "type": "parametric",
                    "golden_table": [{"input": {}, "expected": 0}],
                },
                {
                    "id": "AC-003",
                    "title": "v",
                    "type": "judgment",
                    "rubric_id": "claude_md_v1",
                },
            ],
        }
    )
    result = evaluate_spec(MINIMAL_GOOD_SPEC, machine_yaml=machine_yaml)
    assert result.scores["machine_verifiability"] == 100


def test_machine_verifiability_partial() -> None:
    machine_yaml = yaml.safe_dump(
        {
            "spec_slug": "x",
            "verification_tier": 1,
            "ac": [
                {"id": "AC-001", "title": "t", "type": "mechanical", "executable_predicate": ""},
                {
                    "id": "AC-002",
                    "title": "u",
                    "type": "mechanical",
                    "executable_predicate": "True",
                },
            ],
        }
    )
    result = evaluate_spec(MINIMAL_GOOD_SPEC, machine_yaml=machine_yaml)
    assert result.scores["machine_verifiability"] == 50


def test_mutation_coverage_set_full() -> None:
    machine_yaml = yaml.safe_dump(
        {
            "spec_slug": "x",
            "verification_tier": 1,
            "mutation_threshold": 85,
            "paths_to_mutate": ["src/x.py"],
            "ac": [],
        }
    )
    result = evaluate_spec(MINIMAL_GOOD_SPEC, machine_yaml=machine_yaml)
    assert result.scores["mutation_coverage_set"] == 100


def test_mutation_coverage_set_partial() -> None:
    machine_yaml = yaml.safe_dump(
        {
            "spec_slug": "x",
            "verification_tier": 1,
            "mutation_threshold": 85,
            "paths_to_mutate": [],
            "ac": [],
        }
    )
    result = evaluate_spec(MINIMAL_GOOD_SPEC, machine_yaml=machine_yaml)
    assert result.scores["mutation_coverage_set"] == 50


def test_mutation_coverage_set_omitted_for_non_python() -> None:
    """Non-Python SPECs (no mutation_threshold) skip the dim entirely.

    Including it as 0 unfairly dragged the overall average for agents/templates
    whose verification path is ADR-009 3-layer (not mutation).
    """
    machine_yaml = yaml.safe_dump({"spec_slug": "x", "verification_tier": 3, "ac": []})
    result = evaluate_spec(MINIMAL_GOOD_SPEC, machine_yaml=machine_yaml)
    assert "mutation_coverage_set" not in result.scores
    # Other machine dims still present
    assert "machine_verifiability" in result.scores
    assert "non_python_intent_alignment" in result.scores


def test_invalid_machine_yaml_zeros_machine_dims() -> None:
    # yaml load failure → the 3 always-on machine dims = 0. oracle_independence
    # is v2-gated and must NOT appear on an invalid spec (REVIEW C-P2): a
    # malformed v1 spec is not penalized on a dim a well-formed v1 spec lacks.
    result = evaluate_spec(MINIMAL_GOOD_SPEC, machine_yaml=":bad: : yaml :")
    for dim in ("machine_verifiability", "mutation_coverage_set", "non_python_intent_alignment"):
        assert result.scores[dim] == 0
    assert "oracle_independence" not in result.scores


def test_overall_includes_machine_dims_in_average() -> None:
    """When machine_yaml is provided AND Python-backed, overall averages 5+3=8 dims."""
    machine_yaml = yaml.safe_dump(
        {
            "spec_slug": "x",
            "verification_tier": 1,
            "mutation_threshold": 85,
            "paths_to_mutate": ["x.py"],
            "ac": [
                {"id": "AC-001", "title": "t", "type": "mechanical", "executable_predicate": "True"}
            ],
        }
    )
    without = evaluate_spec(MINIMAL_GOOD_SPEC)
    with_yaml = evaluate_spec(MINIMAL_GOOD_SPEC, machine_yaml=machine_yaml)
    # 8 dims (Python) vs 5 dims (no machine yaml)
    assert len(with_yaml.scores) == 8
    assert len(without.scores) == 5


def test_non_python_omits_mutation_dim_in_average() -> None:
    """Non-Python machine yaml averages 5+2=7 dims (mutation_coverage_set omitted)."""
    machine_yaml = yaml.safe_dump(
        {
            "spec_slug": "x",
            "verification_tier": 1,
            "mutation_threshold": None,
            "paths_to_mutate": [],
            "ac": [{"id": "AC-001", "title": "t", "type": "judgment", "rubric_id": "x"}],
        }
    )
    result = evaluate_spec(MINIMAL_GOOD_SPEC, machine_yaml=machine_yaml)
    assert len(result.scores) == 7  # 5 narrative + 2 machine (mutation omitted)
