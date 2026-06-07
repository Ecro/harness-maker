"""Phase 3 — preset matrix on plan-validator in second_opinion_codex partial (ADR-002/003).

enabled=True:
  Production -> plan-validator ALWAYS mandatory.
  Side      -> plan-validator mandatory iff high-diff (run high_diff classify).
Array reviewers (code-reviewer, consensus-arbiter) keep opt-in MAY until P4b
(their array output cannot host the reconciliation envelope yet — ADR-001).
Skip-receipts append to the ADR-005 ledger (best-effort), all enabled agents.
"""

from __future__ import annotations

from harness_maker.render import _make_env

_PARTIAL = "agents/_partials/second_opinion_codex.md.j2"


def _render_partial(*, name: str, enabled: bool, preset: str) -> str:
    env = _make_env()
    config = {
        "codex_second_opinion": {
            "enabled": enabled,
            "agents": ["code-reviewer", "consensus-arbiter", "plan-validator"],
            "hermetic": True,
            "output_schema_path": ".claude/schemas/codex-finding.schema.json",
        },
        "preset": preset,
    }
    return env.get_template(_PARTIAL).render(config=config, name=name)


def test_production_plan_validator_always_mandatory() -> None:
    out = _render_partial(name="plan-validator", enabled=True, preset="Production")
    assert "## Required: Codex second opinion" in out
    assert "MUST" in out
    assert "codex_reconciliation" in out  # envelope preserved
    assert "high_diff" not in out  # Production = always; no high-diff gate


def test_side_plan_validator_is_high_diff_gated() -> None:
    out = _render_partial(name="plan-validator", enabled=True, preset="Side")
    assert "high_diff classify" in out
    assert "high-diff" in out.lower()
    assert "codex_reconciliation" in out  # envelope still present on Side


def test_reviewers_stay_optional_regardless_of_preset() -> None:
    for preset in ("Production", "Side"):
        out = _render_partial(name="code-reviewer", enabled=True, preset=preset)
        assert "## Optional: Codex second opinion" in out
        assert "opt-in per call" in out
        assert "codex_reconciliation" not in out


def test_skip_receipt_emitted_for_all_enabled_agents() -> None:
    for name in ("plan-validator", "code-reviewer", "consensus-arbiter"):
        out = _render_partial(name=name, enabled=True, preset="Production")
        assert "codex_ledger emit" in out


def test_disabled_is_byte_zero() -> None:
    out = _render_partial(name="plan-validator", enabled=False, preset="Production")
    assert out == ""  # literal byte-zero (ADR-007 P-W1), not whitespace-tolerant


def test_agent_not_in_list_is_byte_zero() -> None:
    out = _render_partial(name="executor", enabled=True, preset="Production")
    assert out == ""
