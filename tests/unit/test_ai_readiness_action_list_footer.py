"""PLAN-fresh-install-p0-calibration: terminal-summary footer rendering.

Phase 2 + ADR-004: when ImprovementPlan carries non-zero deferred_telemetry
or demoted_governance counts, render_terminal_summary appends a one-line
footer explaining the suppressed/demoted items.
"""

from __future__ import annotations

from harness_maker.ai_readiness import render_terminal_summary
from harness_maker.improvement import ActionItem, ImprovementPlan


def _plan(
    *,
    actions: list[ActionItem] | None = None,
    deferred_telemetry: int = 0,
    demoted_governance: int = 0,
) -> ImprovementPlan:
    return ImprovementPlan(
        composite_score=60,
        layer_scores={"readiness": 60, "llm_judge": 50, "cache": 50},
        actions=actions or [],
        deferred_telemetry=deferred_telemetry,
        demoted_governance=demoted_governance,
    )


def _action(priority: str, dim: str, summary: str, source: str) -> ActionItem:
    return ActionItem(
        priority=priority,
        dimension=dim,
        target=dim,
        summary=summary,
        detail=f"signal {source} failed",
        suggestion=f"fix {dim}",
        source=source,
    )


def test_footer_absent_when_counters_zero() -> None:
    plan = _plan(
        actions=[_action("P1", "verification", "no tests", "layer1:ci_invokes_tests")],
        deferred_telemetry=0,
        demoted_governance=0,
    )
    output = render_terminal_summary(plan)
    assert "deferred" not in output.lower()


def test_footer_present_when_telemetry_deferred() -> None:
    plan = _plan(
        actions=[_action("P0", "context_quality", "no CLAUDE.md", "layer1:claude_md_present")],
        deferred_telemetry=2,
        demoted_governance=0,
    )
    output = render_terminal_summary(plan)
    assert "2 telemetry" in output
    assert "auto-populate" in output


def test_footer_present_when_governance_demoted() -> None:
    plan = _plan(
        actions=[
            _action("P2", "governance", "No ADRs in docs/adr/", "layer1:adr_present"),
        ],
        deferred_telemetry=0,
        demoted_governance=1,
    )
    output = render_terminal_summary(plan)
    assert "1 aspirational" in output or "1 aspirational governance" in output
    assert "P2" in output


def test_footer_present_when_both_categories_active() -> None:
    plan = _plan(
        actions=[
            _action("P2", "governance", "No ADRs", "layer1:adr_present"),
        ],
        deferred_telemetry=2,
        demoted_governance=3,
    )
    output = render_terminal_summary(plan)
    # Single consolidated footer line — not duplicated per category.
    deferred_lines = [line for line in output.splitlines() if "deferred" in line.lower()]
    assert len(deferred_lines) == 1
    assert "2 telemetry" in deferred_lines[0]
    assert "3 aspirational" in deferred_lines[0]
    assert "/hm:health" in deferred_lines[0]


def test_footer_present_when_no_actions_remain() -> None:
    """Edge: counters > 0 but actions list is empty (everything filtered).

    The footer must still appear so the user understands why the action list
    looks empty despite a low composite score.
    """
    plan = _plan(
        actions=[],
        deferred_telemetry=2,
        demoted_governance=0,
    )
    output = render_terminal_summary(plan)
    assert "No actions" not in output, "the bare 'No actions' message hides the deferral context"
    assert "2 telemetry" in output


def test_footer_renders_after_action_list() -> None:
    """Format: footer line appears AFTER the Top-N action block, not before."""
    plan = _plan(
        actions=[_action("P0", "context_quality", "no CLAUDE.md", "layer1:claude_md_present")],
        deferred_telemetry=1,
        demoted_governance=1,
    )
    output = render_terminal_summary(plan)
    lines = output.splitlines()
    action_line_idx = next(i for i, line in enumerate(lines) if "[P0]" in line)
    footer_line_idx = next(i for i, line in enumerate(lines) if "deferred" in line.lower())
    assert footer_line_idx > action_line_idx
