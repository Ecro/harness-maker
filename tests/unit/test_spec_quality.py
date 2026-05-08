"""Tests for spec strength rubric (Phase 9)."""

from __future__ import annotations

from harness_maker.models import DevMode
from harness_maker.spec_quality import evaluate_spec

STRONG_SPEC = """\
## Scope
In-scope: User authentication feature with OAuth2.
Out-of-scope: Payment processing, admin panel.
Non-goal: Mobile app support.

## Requirements
- Feature: Login via Google OAuth2
- Constraint: Token expiry < 1h
- Edge case: Revoked token handling

## Acceptance Criteria
- THEN: User receives valid JWT
- Verify: Token contains user email
- Assert: Expired tokens return 401
- Test: Integration test for full flow
- Observable: Login count metric incremented
"""

WEAK_SPEC = """\
Make the app fast and good.
It should be better than before and work properly.
The important things should be nice and adequate.
"""

MODERATE_SPEC = """\
## Scope
Build a REST API for user management.

## Acceptance Criteria
- Verify: Users can be created
- Test: Unit tests pass
"""


def test_strong_spec_high_score() -> None:
    result = evaluate_spec(STRONG_SPEC)
    assert result.overall >= 60
    assert not result.is_weak


def test_weak_spec_low_score() -> None:
    result = evaluate_spec(WEAK_SPEC)
    assert result.is_weak
    assert len(result.weak_dimensions) > 0


def test_spec_driven_blocks_weak_spec() -> None:
    result = evaluate_spec(WEAK_SPEC, dev_mode=DevMode.SPEC_DRIVEN)
    assert result.blocked is True


def test_task_driven_does_not_block_weak_spec() -> None:
    result = evaluate_spec(WEAK_SPEC, dev_mode=DevMode.TASK_DRIVEN)
    assert result.blocked is False
    assert result.is_weak


def test_spec_driven_allows_strong_spec() -> None:
    result = evaluate_spec(STRONG_SPEC, dev_mode=DevMode.SPEC_DRIVEN)
    assert result.blocked is False


def test_scores_have_all_dimensions() -> None:
    result = evaluate_spec(MODERATE_SPEC)
    assert "completeness" in result.scores
    assert "testability" in result.scores
    assert "unambiguity" in result.scores
    assert "consistency" in result.scores
    assert "scope_boundary" in result.scores


def test_dev_mode_string_accepted() -> None:
    result = evaluate_spec(MODERATE_SPEC, dev_mode="task-driven")
    assert result.dev_mode == "task-driven"


def test_unknown_dev_mode_defaults_to_task_driven() -> None:
    result = evaluate_spec(MODERATE_SPEC, dev_mode="unknown-mode")
    assert result.dev_mode == "task-driven"
    assert result.blocked is False


def test_empty_spec_is_weak() -> None:
    result = evaluate_spec("")
    assert result.is_weak


def test_vague_terms_reduce_unambiguity() -> None:
    vague = "This should be fast and good and important and better"
    result = evaluate_spec(vague)
    assert result.scores["unambiguity"] < 60
