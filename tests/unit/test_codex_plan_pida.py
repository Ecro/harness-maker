"""plan-validator PIDA reconciliation flow (PLAN-crossmodel-codex-gaps ADR-004).

PLAN-codex-second-opinion-sandbox ADR-002/005: the exec recipe moved to the main
loop; the *non-exec* reconciliation contract (PIDA debate flow + output envelope)
was re-homed into the plan-validator agent BODY (it has no Bash and never runs
Codex — it reconciles the main-loop-injected findings).

Codex finding -> Claude rebuttal (KEEP/REFUTE) -> oracle decides if one exists,
else mark [unresolved] and surface. No-oracle short-circuit (plan has no test
oracle). overall_assessment stays Claude's; [unresolved] never blocks.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import (
    CodexSecondOpinionConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render_plan_validator(tmp_path: Path, *, preset: Preset = Preset.PRODUCTION) -> str:
    """Full synthesize -> render path; return the rendered plan-validator agent body."""
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=preset,
            targets=[Target.CLAUDE_CODE],
            codex_second_opinion=CodexSecondOpinionConfig(enabled=True),
        ),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return (tmp_path / "agents" / "plan-validator.md").read_text(encoding="utf-8")


def test_unresolved_disposition_present(tmp_path: Path) -> None:
    assert "unresolved" in _render_plan_validator(tmp_path)


def test_pida_rebuttal_keep_refute(tmp_path: Path) -> None:
    out = _render_plan_validator(tmp_path)
    assert "KEEP" in out
    assert "REFUTE" in out


def test_oracle_or_unresolved(tmp_path: Path) -> None:
    low = _render_plan_validator(tmp_path).lower()
    assert "oracle" in low
    assert "unresolved" in low


def test_no_oracle_short_circuit(tmp_path: Path) -> None:
    """When no oracle exists, skip the rebuttal and go straight to [unresolved]."""
    low = _render_plan_validator(tmp_path).lower()
    assert "no oracle" in low or "without an oracle" in low or "no test oracle" in low


def test_overall_assessment_stays_claude(tmp_path: Path) -> None:
    out = _render_plan_validator(tmp_path)
    assert "overall_assessment" in out
    low = out.lower()
    assert "never block" in low or "not block" in low


def test_reconcile_block_byte_zero_when_disabled(tmp_path: Path) -> None:
    """Disabled render carries no reconciliation contract (absent-case rule)."""
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE],
            codex_second_opinion=CodexSecondOpinionConfig(enabled=False),
        ),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    body = (tmp_path / "agents" / "plan-validator.md").read_text(encoding="utf-8")
    assert "@hm:codex-reconcile" not in body
    assert "codex_reconciliation" not in body
    assert "codex exec" not in body
