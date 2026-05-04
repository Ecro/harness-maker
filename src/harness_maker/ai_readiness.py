"""Orchestrator — combine all 3 readiness layers into a plan + renders.

Public API:
- ``run_ai_readiness(project_dir, preset, ...)`` — full pipeline returning
  ``ImprovementPlan``. Layer 2 (LLM) runs by default against rubrics shipped
  under ``.claude/rubrics/``; skip with ``skip_llm=True`` for offline runs.
- ``render_terminal_summary(plan)`` — concise text for CLI output.
- ``render_dashboard_markdown(plan, project_name)`` — dashboard.md content.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.cache_diagnostics import diagnose_cache
from harness_maker.improvement import ActionItem, ImprovementPlan, build_improvement_plan
from harness_maker.llm_judge import (
    AnthropicJudgeClient,
    JudgeClient,
    JudgeResult,
    judge_target,
)
from harness_maker.models import Preset
from harness_maker.readiness import compute_readiness
from harness_maker.rubric_loader import load_rubrics


def _build_judge_client() -> JudgeClient | None:
    """Best-effort construction of an Anthropic-backed judge.

    Returns None when the SDK can't initialize (missing API key, network
    unreachable on import, etc.) — the orchestrator falls back to skipping
    Layer 2 silently rather than failing the whole readiness check.
    """
    try:
        return AnthropicJudgeClient()
    except Exception:  # noqa: BLE001 — optional dependency at runtime
        return None


def run_ai_readiness(
    project_dir: Path,
    *,
    preset: Preset,
    skip_llm: bool = False,
    judge_client: JudgeClient | None = None,
    model: str = "claude-sonnet-4-6",
) -> ImprovementPlan:
    """Run the 3-layer pipeline and return a composite improvement plan."""
    readiness = compute_readiness(project_dir, preset)
    metrics = project_dir / ".claude" / "observability" / "metrics.jsonl"
    cache = diagnose_cache(metrics, model=model)

    judge_results: list[JudgeResult] = []
    if not skip_llm:
        rubrics = load_rubrics(project_dir / ".claude" / "rubrics")
        if rubrics:
            client = judge_client or _build_judge_client()
            if client is not None:
                for rf in rubrics.values():
                    judge_results.extend(judge_target(project_dir, rf, client=client, model=model))

    return build_improvement_plan(readiness, judge_results, cache)


def render_terminal_summary(plan: ImprovementPlan, *, max_actions: int = 10) -> str:
    """Concise text suitable for stdout when /hm:ai-readiness is invoked."""
    lines = [
        f"ai-readiness: {plan.composite_score} / 100",
        "",
        "Layer scores:",
        f"  readiness  : {plan.layer_scores['readiness']:>3}  (deterministic structural)",
        f"  llm_judge  : {plan.layer_scores['llm_judge']:>3}  (LLM content quality)",
        f"  cache      : {plan.layer_scores['cache']:>3}  (prompt-caching efficiency)",
        "",
    ]
    if not plan.actions:
        lines.append("No actions — project looks healthy.")
        return "\n".join(lines)

    lines.append(f"Top {min(max_actions, len(plan.actions))} of {len(plan.actions)} actions:")
    for a in plan.actions[:max_actions]:
        lines.append(f"  [{a.priority}] {a.dimension} :: {a.summary}")
        lines.append(f"        → {a.suggestion}")
    if len(plan.actions) > max_actions:
        lines.append(f"  … {len(plan.actions) - max_actions} more (run --verbose for full list)")
    return "\n".join(lines)


def _format_action_row(a: ActionItem) -> str:
    suggestion = a.suggestion.replace("|", r"\|").replace("\n", " ")
    summary = a.summary.replace("|", r"\|").replace("\n", " ")
    return f"| {a.priority} | {a.dimension} | {summary} | {suggestion} |"


def render_dashboard_markdown(plan: ImprovementPlan, project_name: str) -> str:
    """Markdown dashboard body for ``.claude/observability/dashboard.md``."""
    lines: list[str] = [
        f"# AI Readiness — {project_name}",
        "",
        f"**Composite:** {plan.composite_score} / 100",
        "",
        "## Layer scores",
        "",
        "| Layer | Score | What it measures |",
        "|-------|------:|------------------|",
        f"| readiness | {plan.layer_scores['readiness']} | "
        "Deterministic structural signals (CLAUDE.md, hooks, tests, CI, …) |",
        f"| llm_judge | {plan.layer_scores['llm_judge']} | "
        "LLM-judged content quality vs rubrics |",
        f"| cache | {plan.layer_scores['cache']} | "
        "Prompt-cache hit rate + failure-mode diagnosis |",
        "",
    ]
    if not plan.actions:
        lines.extend(["## Actions", "", "(none — project looks healthy)", ""])
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "## Actions",
            "",
            "| Priority | Dimension | Summary | Suggestion |",
            "|----------|-----------|---------|------------|",
        ]
    )
    for a in plan.actions:
        lines.append(_format_action_row(a))
    lines.append("")
    return "\n".join(lines) + "\n"
