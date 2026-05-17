"""PLAN-antisycophancy-2026-05 Phase 2 + Phase 7 tests.

Five named test cases covering the variant resolver behaviour
(full / reframe / soft / missing / invalid). ADR-002 forbids
default-to-FULL — missing variant must be a loud render-time error.
"""

from __future__ import annotations

import pytest
from jinja2 import TemplateNotFound, UndefinedError

from harness_maker.render import (
    _extract_source_communication_variant,
    _make_env,
)

_FULL_CONFIG = {
    "reviewers": {"verbosity": "standard"},
    "project": {"domains": []},
    "work_docs": {"dir": "work-docs/"},
    "spec": {"dir": "specs/"},
    "dev_mode": "task-driven",
}

_REVIEWER_KINDS: dict[str, str] = {
    "code-reviewer": "code",
    "security-reviewer": "security",
    "performance-reviewer": "performance",
    "concurrency-reviewer": "concurrency",
    "ux-reviewer": "ux",
}


def _render_dispatcher(name: str) -> str:
    env = _make_env()
    variant = _extract_source_communication_variant(f"agents/{name}.md.j2", env)
    tpl = env.get_template(f"agents/{name}.md.j2")
    return tpl.render(
        name=name,
        reviewer_kind=_REVIEWER_KINDS.get(name, ""),
        config=_FULL_CONFIG,
        communication_variant=variant,
    )


def test_variant_full_renders_full_partial() -> None:
    rendered = _render_dispatcher("autoloop-coder")
    assert '- Be direct. No flattery, no preamble, no "Great question!"' in rendered
    assert "<!-- @hm:communication_variant: full -->" in rendered
    assert "## Input Processing" not in rendered
    assert "<!-- @hm:communication_variant: soft -->" not in rendered


def test_variant_reframe_renders_reframe_partial() -> None:
    rendered = _render_dispatcher("code-reviewer")
    assert '- Be direct. No flattery, no preamble, no "Great question!"' in rendered
    assert "## Input Processing" in rendered
    assert "reframe the submission internally as a question" in rendered
    assert "<!-- @hm:communication_variant: reframe -->" in rendered
    assert "<!-- @hm:communication_variant: full -->" not in rendered


def test_variant_soft_renders_soft_partial() -> None:
    env = _make_env()
    partial = env.get_template("agents/_partials/communication_soft.md.j2")
    rendered = partial.render()
    assert "## Honesty Protocol" in rendered
    assert "Excitement and honesty are not mutually exclusive" in rendered
    assert "<!-- @hm:communication_variant: soft -->" in rendered


def test_variant_missing_raises_explicit_error() -> None:
    """ADR-002: no default-to-FULL. Missing variant → loud render-time error."""
    env = _make_env()
    template_text = (
        '{% include "agents/_partials/communication_"'
        ' ~ communication_variant ~ ".md.j2" %}'
    )
    tpl = env.from_string(template_text)
    with pytest.raises(UndefinedError):
        tpl.render()


def test_variant_invalid_value_raises() -> None:
    env = _make_env()
    template_text = (
        '{% include "agents/_partials/communication_"'
        ' ~ communication_variant ~ ".md.j2" %}'
    )
    tpl = env.from_string(template_text)
    with pytest.raises(TemplateNotFound):
        tpl.render(communication_variant="hard")
