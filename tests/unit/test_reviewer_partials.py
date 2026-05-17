"""Tests for reviewer agent partials in templates/agents/_partials/.

Why these are testable: each partial reads ``config.reviewers.verbosity`` and
``reviewer_kind`` from context. Rendering the partial directly under different
verbosities is the cleanest way to lock in the ``terse | standard | full`` tier
shape without round-tripping through synthesize.
"""

from __future__ import annotations

import pytest

from harness_maker.render import _make_env

REVIEWERS = [
    "code-reviewer",
    "security-reviewer",
    "performance-reviewer",
    "concurrency-reviewer",
    "ux-reviewer",
]
KINDS = {
    "code-reviewer": "code",
    "security-reviewer": "security",
    "performance-reviewer": "performance",
    "concurrency-reviewer": "concurrency",
    "ux-reviewer": "ux",
}


def _render_reviewer(name: str, verbosity: str) -> str:
    env = _make_env()
    tpl = env.get_template(f"agents/{name}.md.j2")
    return tpl.render(
        name=name,
        reviewer_kind=KINDS[name],
        config={
            "reviewers": {"verbosity": verbosity},
            "project": {"domains": []},
        },
        communication_variant="reframe",
    )


@pytest.mark.parametrize("name", REVIEWERS)
def test_each_reviewer_includes_all_four_partials(name: str) -> None:
    body = _render_reviewer(name, "standard")
    assert "## Severity Rubric" in body
    assert "## Reasoning Template" in body
    assert "## Hard Rules" in body
    assert "## Finding Schema" in body


@pytest.mark.parametrize("name", REVIEWERS)
def test_terse_verbosity_drops_p2_p3_and_reasoning(name: str) -> None:
    body = _render_reviewer(name, "terse")
    assert "P0" in body
    assert "P1" in body
    # P2 entry in the rubric should be gated out (the should-fix bullet absent).
    assert "should-fix" not in body
    assert "P3" not in body
    # Reasoning template entirely omitted in terse.
    assert "Reasoning Template" not in body


@pytest.mark.parametrize("name", REVIEWERS)
def test_full_verbosity_adds_p3_and_rationale(name: str) -> None:
    body = _render_reviewer(name, "full")
    assert "P3" in body
    assert "rationale" in body


def test_security_schema_has_category_field() -> None:
    body = _render_reviewer("security-reviewer", "standard")
    assert "`category`" in body
    assert "secrets" in body


def test_concurrency_schema_has_race_kind() -> None:
    body = _render_reviewer("concurrency-reviewer", "standard")
    assert "race_kind" in body
    assert "data-race" in body


def test_ux_schema_has_wcag_ref() -> None:
    body = _render_reviewer("ux-reviewer", "standard")
    assert "wcag_ref" in body


def test_performance_schema_has_expected_impact() -> None:
    body = _render_reviewer("performance-reviewer", "standard")
    assert "expected_impact" in body


def test_code_reviewer_has_no_specialty_fields() -> None:
    """Generic reviewer keeps the common envelope only."""
    body = _render_reviewer("code-reviewer", "standard")
    assert "race_kind" not in body
    assert "wcag_ref" not in body
    assert "expected_impact" not in body


# ──────────────────────────────────────────────────────────────────────────────
# Domain pack inlining via {% for d in config.project.domains %}
# ──────────────────────────────────────────────────────────────────────────────


def _render_with_domains(name: str, domains: list[str]) -> str:
    env = _make_env()
    tpl = env.get_template(f"agents/{name}.md.j2")
    return tpl.render(
        name=name,
        reviewer_kind=KINDS[name],
        config={
            "reviewers": {"verbosity": "standard"},
            "project": {"domains": domains},
        },
        communication_variant="reframe",
    )


@pytest.mark.parametrize("name", REVIEWERS)
def test_python_pack_inlined_when_enabled(name: str) -> None:
    body = _render_with_domains(name, ["python"])
    assert "## python standards" in body
    assert "Atomic file writes only" in body


@pytest.mark.parametrize("name", REVIEWERS)
def test_no_domain_pack_when_domains_empty(name: str) -> None:
    body = _render_with_domains(name, [])
    assert "## python standards" not in body


@pytest.mark.parametrize("name", REVIEWERS)
def test_unknown_domain_silently_skipped(name: str) -> None:
    """ignore missing — unshipped domain renders nothing without erroring."""
    body = _render_with_domains(name, ["does-not-exist"])
    assert "does-not-exist" not in body
