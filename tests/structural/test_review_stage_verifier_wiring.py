"""Phase A3 — review stage template wires the verifier and Pass-2 invariant.

PLAN-llm-code-review-2026 ADR-002 inserts the verifier at Pass 1.5. The stage
template must:
1. Reference the verifier CLI sub-step between Pass 1 and Pass 2.
2. Identify Pass 2's input as the verifier-kept set, not raw Pass 1.
3. Carry the Pass-2 invariant "MUST NOT re-evaluate verifier-dropped findings".

These checks run on the *rendered* stage so we catch Jinja2 conditionals that
short-circuit (e.g., an `{% if is_codex %}` that swallows the bash line in CC
mode).
"""

from __future__ import annotations

import pytest

from harness_maker.render import _make_env


@pytest.fixture(scope="module")
def rendered_review_cc() -> str:
    env = _make_env()
    tpl = env.get_template("stages/review.md.j2")
    return tpl.render(
        workflow_context="",
        stage="review",
        project_name="",
        feature="",
        config={
            "reviewers": {},
            "work_docs": {"dir": "work-docs/"},
            "spec": {"dir": "specs/"},
        },
        is_codex=False,
    )


@pytest.fixture(scope="module")
def rendered_review_codex() -> str:
    env = _make_env()
    tpl = env.get_template("stages/review.md.j2")
    return tpl.render(
        workflow_context="",
        stage="review",
        project_name="",
        feature="",
        config={
            "reviewers": {},
            "work_docs": {"dir": "work-docs/"},
            "spec": {"dir": "specs/"},
        },
        is_codex=True,
    )


def test_review_stage_includes_verifier_substep(rendered_review_cc: str) -> None:
    """Pass 1.5 verifier sub-step is present in the rendered stage."""
    assert "Pass 1.5" in rendered_review_cc, "verifier sub-step missing in rendered review stage"
    assert "two_pass_review verify" in rendered_review_cc, (
        "verifier CLI invocation missing"
    )
    assert "REDUCE-ONLY" in rendered_review_cc or "reduce-only" in rendered_review_cc, (
        "reduce-only contract not surfaced in verifier sub-step"
    )


def test_review_stage_pass2_invariant_present(rendered_review_cc: str) -> None:
    """Pass 2 must explicitly take the verifier-kept set, not raw Pass 1.

    Guards ADR-002 invariant: Pass 2 MUST NOT re-introduce verifier-dropped
    findings.
    """
    assert "MUST NOT re-evaluate verifier-dropped" in rendered_review_cc, (
        "Pass-2 invariant 'MUST NOT re-evaluate verifier-dropped findings' missing"
    )
    assert "verifier-kept" in rendered_review_cc, (
        "Pass 2 input must be identified as the verifier-kept set"
    )


def test_review_stage_codex_variant_uses_bash_helper(rendered_review_codex: str) -> None:
    """Codex render uses Bash(...) wrapper for the verifier CLI per wiki:codex-is-codex-flag."""
    assert 'Bash("echo' in rendered_review_codex, (
        "Codex variant should wrap verifier CLI in Bash(...) per is_codex pattern"
    )
    assert "two_pass_review verify" in rendered_review_codex


def test_review_stage_preserves_existing_passes(rendered_review_cc: str) -> None:
    """Inserting Pass 1.5 must not have dropped Pass 1 / Pass 2 / merge CLI lines."""
    assert "Pass 1 — rubric-only" in rendered_review_cc
    assert "Pass 2 — contextual verdict" in rendered_review_cc
    assert "two_pass_review redact" in rendered_review_cc
    assert "two_pass_review merge" in rendered_review_cc


def test_review_stage_telemetry_emit_wired(rendered_review_cc: str) -> None:
    """Phase A4 wiring — telemetry CLI invocation present in rendered stage."""
    assert "review_telemetry emit" in rendered_review_cc, (
        "telemetry emitter not wired into review stage"
    )
    assert "review-{YYYY-MM-DD}.jsonl" in rendered_review_cc, (
        "stage must reference daily-rotated observability path"
    )
