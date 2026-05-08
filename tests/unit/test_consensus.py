"""Tests for consensus scope-aware fix (Phase 5)."""

from __future__ import annotations

from harness_maker.conditional_router import (
    REVIEWER_SCOPES,
    is_in_reviewer_scope,
    scope_aware_consensus,
)


def test_reviewer_scopes_defined() -> None:
    assert "code-reviewer" in REVIEWER_SCOPES
    assert "security-reviewer" in REVIEWER_SCOPES
    assert "performance-reviewer" in REVIEWER_SCOPES
    assert "ux-reviewer" in REVIEWER_SCOPES
    assert "concurrency-reviewer" in REVIEWER_SCOPES


def test_is_in_reviewer_scope_security() -> None:
    assert is_in_reviewer_scope("security-reviewer", "auth bypass vulnerability")
    assert is_in_reviewer_scope("security-reviewer", "injection risk")
    assert not is_in_reviewer_scope("security-reviewer", "performance regression")


def test_is_in_reviewer_scope_performance() -> None:
    assert is_in_reviewer_scope("performance-reviewer", "performance hotspot")
    assert not is_in_reviewer_scope("performance-reviewer", "security issue")


def test_is_in_reviewer_scope_unknown_reviewer() -> None:
    assert not is_in_reviewer_scope("unknown-reviewer", "anything")


def test_consensus_two_reviewers_agree() -> None:
    findings = [
        {
            "file": "auth.py",
            "line": 10,
            "severity": "P0",
            "summary": "Missing validation",
            "reviewer": "code-reviewer",
        },
        {
            "file": "auth.py",
            "line": 10,
            "severity": "P0",
            "summary": "Missing validation (similar)",
            "reviewer": "security-reviewer",
        },
    ]
    result = scope_aware_consensus(findings)
    assert len(result) == 1
    assert result[0]["consensus_tag"] == "consensus-passed"
    assert result[0]["consensus_count"] == 2


def test_consensus_single_reviewer_in_scope_exempted() -> None:
    """Security-reviewer's security finding with no other scope overlap → scope-exempted."""
    findings = [
        {
            "file": "auth.py",
            "line": 10,
            "severity": "P0",
            "summary": "Secret key exposed",
            "category": "secrets exposure",
            "reviewer": "security-reviewer",
        },
    ]
    result = scope_aware_consensus(findings)
    assert len(result) == 1
    assert result[0]["consensus_tag"] == "scope-exempted"
    assert result[0]["scope_owner"] == "security-reviewer"


def test_consensus_single_reviewer_out_of_scope_manual() -> None:
    """Security-reviewer opining on performance → manual-only."""
    findings = [
        {
            "file": "hot_path.py",
            "line": 5,
            "severity": "P1",
            "summary": "Slow loop",
            "category": "performance optimization",
            "reviewer": "security-reviewer",
        },
    ]
    result = scope_aware_consensus(findings)
    assert len(result) == 1
    assert result[0]["consensus_tag"] == "manual-only"


def test_consensus_single_code_finding_is_manual() -> None:
    """code-reviewer's 'code' category finding — code-reviewer's scope covers 'code',
    but other reviewers don't cover 'code' exclusively → scope-exempted."""
    findings = [
        {
            "file": "utils.py",
            "line": 20,
            "severity": "P1",
            "summary": "Incorrect logic",
            "category": "code correctness issue",
            "reviewer": "code-reviewer",
        },
    ]
    result = scope_aware_consensus(findings)
    assert len(result) == 1
    assert result[0]["consensus_tag"] == "scope-exempted"


def test_consensus_concurrency_scope_exempted() -> None:
    """concurrency-reviewer's race condition finding → scope-exempted."""
    findings = [
        {
            "file": "worker.py",
            "line": 30,
            "severity": "P0",
            "summary": "Data race on shared state",
            "category": "race condition in worker pool",
            "reviewer": "concurrency-reviewer",
        },
    ]
    result = scope_aware_consensus(findings)
    assert len(result) == 1
    assert result[0]["consensus_tag"] == "scope-exempted"


def test_consensus_preserves_all_independent_findings() -> None:
    findings = [
        {
            "file": "a.py",
            "line": 1,
            "severity": "P1",
            "summary": "Issue A",
            "category": "code quality",
            "reviewer": "code-reviewer",
        },
        {
            "file": "b.py",
            "line": 2,
            "severity": "P0",
            "summary": "Issue B",
            "category": "security auth bypass",
            "reviewer": "security-reviewer",
        },
    ]
    result = scope_aware_consensus(findings)
    assert len(result) == 2


def test_grade_impact_of_scope_exempted() -> None:
    """Scope-exempted findings should be treated like consensus-passed for grading."""
    findings = [
        {
            "file": "auth.py",
            "line": 10,
            "severity": "P0",
            "summary": "Auth bypass",
            "category": "auth vulnerability",
            "reviewer": "security-reviewer",
        },
    ]
    result = scope_aware_consensus(findings)
    assert result[0]["consensus_tag"] == "scope-exempted"
