"""plan-validator PIDA reconciliation flow (PLAN-crossmodel-codex-gaps ADR-004,
generalized to multi-model by PLAN-second-opinion-multi-model).

PLAN-codex-second-opinion-sandbox ADR-002/005: the exec recipe moved to the main
loop; the *non-exec* reconciliation contract (PIDA debate flow + output envelope)
was re-homed into the plan-validator agent BODY (it has no Bash and never runs
any second-opinion CLI — it reconciles the main-loop-injected findings). The output
envelope is now the `second_opinion_results` array (one entry per enabled model),
superseding the old scalar `codex_status`/`codex_reconciliation` fields.

Second-opinion finding -> Claude rebuttal (KEEP/REFUTE) -> oracle decides if one
exists, else mark [unresolved] and surface. No-oracle short-circuit (plan has no
test oracle). overall_assessment stays Claude's; [unresolved] never blocks.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import (
    InterviewAnswers,
    Preset,
    ProjectProfile,
    SecondOpinionConfig,
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
            second_opinion=SecondOpinionConfig(models=["codex"]),
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


def test_second_opinion_results_array_contract(tmp_path: Path) -> None:
    """Output envelope is the `second_opinion_results` array of {model, status,
    reconciliation} — supersedes the old scalar codex_status/codex_reconciliation
    fields (rename mapping)."""
    out = _render_plan_validator(tmp_path)
    assert "second_opinion_results" in out
    assert '"model"' in out
    assert '"status"' in out
    assert '"reconciliation"' in out
    assert "codex_status" not in out
    assert "codex_reconciliation" not in out


def test_reconcile_block_byte_zero_when_disabled(tmp_path: Path) -> None:
    """Disabled render carries no reconciliation contract (absent-case rule)."""
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE],
            second_opinion=SecondOpinionConfig(),  # models=[] — feature off
        ),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    body = (tmp_path / "agents" / "plan-validator.md").read_text(encoding="utf-8")
    assert "@hm:second-opinion-reconcile" not in body
    assert "second_opinion_results" not in body
    assert "codex exec" not in body
