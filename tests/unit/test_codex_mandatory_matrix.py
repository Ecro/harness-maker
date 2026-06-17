"""Codex mandatory-matrix after the main-loop cutover (PLAN-codex-second-opinion-sandbox).

ADR-002/003/005 moved the Codex exec + mandatory gate into the plan STAGE main loop;
the plan-validator AGENT keeps only the non-exec reconciliation envelope.

  Production -> plan stage runs Codex on every validation (no high-diff gate).
  Side       -> plan stage runs Codex only on a high-diff change (high_diff classify).
  Both       -> plan-validator agent carries the codex_reconciliation envelope.
  Reviewers (code-reviewer, consensus-arbiter) carry NO exec recipe / envelope.
  Ledger emit lives in the review + plan STAGES, not the agents.
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


def _render(tmp_path: Path, *, preset: Preset, enabled: bool) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=preset,
            targets=[Target.CLAUDE_CODE],
            codex_second_opinion=CodexSecondOpinionConfig(enabled=enabled),
        ),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    out: dict[str, str] = {}
    for f in tmp_path.rglob("*.md"):
        out[str(f.relative_to(tmp_path))] = f.read_text(encoding="utf-8")
    return out


def _plan_stage(files: dict[str, str]) -> str:
    return next(t for p, t in files.items() if p.endswith("stages/plan.md"))


def _review_stage(files: dict[str, str]) -> str:
    return next(t for p, t in files.items() if p.endswith("stages/review.md"))


def _agent(files: dict[str, str], name: str) -> str:
    return files[f"agents/{name}.md"]


def test_production_plan_stage_always_mandatory(tmp_path: Path) -> None:
    files = _render(tmp_path, preset=Preset.PRODUCTION, enabled=True)
    plan = _plan_stage(files)
    assert "run Codex on **every**" in plan
    assert "high_diff" not in plan  # Production = always; no high-diff gate
    # envelope still owned by the agent
    assert "codex_reconciliation" in _agent(files, "plan-validator")


def test_side_plan_stage_is_high_diff_gated(tmp_path: Path) -> None:
    files = _render(tmp_path, preset=Preset.SIDE, enabled=True)
    plan = _plan_stage(files)
    assert "high_diff classify" in plan
    assert "high-diff" in plan.lower()
    assert "codex_reconciliation" in _agent(files, "plan-validator")


def test_reviewers_carry_no_exec_or_envelope(tmp_path: Path) -> None:
    files = _render(tmp_path, preset=Preset.PRODUCTION, enabled=True)
    for name in ("code-reviewer", "consensus-arbiter"):
        body = _agent(files, name)
        assert "codex exec" not in body, f"{name} still carries a codex exec recipe"
        assert "codex_reconciliation" not in body, f"reconciliation envelope leaked into {name}"
        assert "@hm:codex-second-opinion" not in body


def test_ledger_emit_lives_in_stages(tmp_path: Path) -> None:
    files = _render(tmp_path, preset=Preset.PRODUCTION, enabled=True)
    assert "codex_ledger emit" in _plan_stage(files)
    assert "codex_ledger emit" in _review_stage(files)
    # not in the agents anymore
    for name in ("plan-validator", "code-reviewer", "consensus-arbiter"):
        assert "codex_ledger emit" not in _agent(files, name), f"ledger emit leaked into {name}"


def test_disabled_is_byte_zero(tmp_path: Path) -> None:
    files = _render(tmp_path, preset=Preset.PRODUCTION, enabled=False)
    plan = _plan_stage(files)
    assert "Step 4 (pre)" not in plan
    assert "dangerouslyDisableSandbox" not in plan
    pv = _agent(files, "plan-validator")
    assert "@hm:codex-reconcile" not in pv
    assert "codex_reconciliation" not in pv


def test_non_codex_agent_has_no_reconcile_block(tmp_path: Path) -> None:
    files = _render(tmp_path, preset=Preset.PRODUCTION, enabled=True)
    body = _agent(files, "security-auditor")
    assert "@hm:codex-reconcile" not in body
    assert "codex_reconciliation" not in body
