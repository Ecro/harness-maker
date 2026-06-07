"""Phase 5 — plan-validator PIDA debate flow (PLAN-crossmodel-codex-gaps ADR-004).

Codex finding -> Claude rebuttal (KEEP/REFUTE) -> oracle decides if one exists,
else mark [unresolved] and surface. No-oracle short-circuit (plan has no test oracle).
overall_assessment stays Claude's; [unresolved] never blocks.
"""

from __future__ import annotations

from harness_maker.render import _make_env

_PARTIAL = "agents/_partials/second_opinion_codex.md.j2"


def _render_plan_validator(*, preset: str = "Production") -> str:
    env = _make_env()
    config = {
        "codex_second_opinion": {
            "enabled": True,
            "agents": ["plan-validator"],
            "hermetic": True,
            "output_schema_path": ".claude/schemas/codex-finding.schema.json",
        },
        "preset": preset,
    }
    return env.get_template(_PARTIAL).render(config=config, name="plan-validator")


def test_unresolved_disposition_present() -> None:
    out = _render_plan_validator()
    assert "unresolved" in out


def test_pida_rebuttal_keep_refute() -> None:
    out = _render_plan_validator()
    assert "KEEP" in out
    assert "REFUTE" in out


def test_oracle_or_unresolved() -> None:
    out = _render_plan_validator()
    low = out.lower()
    assert "oracle" in low
    assert "unresolved" in low


def test_no_oracle_short_circuit() -> None:
    """W6 resolution: when no oracle exists, skip the rebuttal and go straight to [unresolved]."""
    out = _render_plan_validator()
    low = out.lower()
    assert "no oracle" in low or "without an oracle" in low or "no test oracle" in low


def test_overall_assessment_stays_claude() -> None:
    out = _render_plan_validator()
    assert "overall_assessment" in out
    # [unresolved] must never block — warn-and-proceed preserved
    low = out.lower()
    assert "never block" in low or "not block" in low
