"""Orchestrator — combine readiness layers into a plan + renders.

PLAN health-consolidation Phase 1 (0.13.0) split the 3-layer composite
score into a ``structural`` field of the unified ``/hm:health`` dashboard.
The new entrypoint ``run_structural(project_dir, preset)`` returns a
minimal ``{"score": int, "signals_failed": [...]}`` dict suitable
for the dashboard third-section writer; the legacy ``run_ai_readiness``
and rendering helpers are retained so existing callers and tests in the
package continue to work until the templates catch up (Phase 2).

Public API:
- ``run_structural(project_dir, preset)`` — NEW, 0.13.0 health field.
- ``run_ai_readiness(project_dir, preset, ...)`` — legacy full pipeline.
- ``run_ai_readiness_structural(project_dir, preset, ...)`` — L1+L3 only.
- ``finalize_from_verdicts_json(scores_path, verdicts_path)`` — legacy.
- ``render_terminal_summary(plan)`` — concise text for CLI output.
- ``render_dashboard_markdown(plan, project_name)`` — legacy dashboard body.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_maker.cache_diagnostics import CacheDiagnosis, diagnose_cache_for_project
from harness_maker.communication_audit import audit_communication
from harness_maker.improvement import ActionItem, ImprovementPlan, build_improvement_plan
from harness_maker.llm_judge import (
    AnthropicJudgeClient,
    JudgeClient,
    JudgeResult,
    RubricVerdict,
    compute_score_from_verdicts,
    judge_target,
)
from harness_maker.models import Preset
from harness_maker.readiness import ReadinessResult, compute_readiness
from harness_maker.rubric_loader import load_rubrics


def _build_judge_client() -> JudgeClient | None:
    """Best-effort Anthropic SDK client (requires ANTHROPIC_API_KEY).

    In Claude Code subscription contexts Layer 2 runs prompt-natively
    (the executing Claude agent evaluates rubrics inline). This fallback
    is kept for non-interactive / CI environments that do have an API key.
    """
    try:
        return AnthropicJudgeClient()
    except Exception:  # noqa: BLE001 — missing API key etc.
        return None


def run_ai_readiness(
    project_dir: Path,
    *,
    preset: Preset,
    skip_llm: bool = False,
    judge_client: JudgeClient | None = None,
    model: str = "claude-sonnet-4-6",
    session_id: str | None = None,
) -> ImprovementPlan:
    """Run the 3-layer pipeline and return a composite improvement plan."""
    readiness = compute_readiness(project_dir, preset, session_id=session_id)
    cache = diagnose_cache_for_project(project_dir, model=model)

    judge_results: list[JudgeResult] = []
    if not skip_llm:
        rubrics = load_rubrics(project_dir / ".claude" / "rubrics")
        if rubrics:
            client = judge_client or _build_judge_client()
            if client is not None:
                for rf in rubrics.values():
                    judge_results.extend(judge_target(project_dir, rf, client=client, model=model))

    return build_improvement_plan(readiness, judge_results, cache)


def run_ai_readiness_structural(
    project_dir: Path,
    *,
    preset: Preset,
    model: str = "claude-sonnet-4-6",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Run L1+L3 only and return a JSON-serializable dict.

    The dict is written by ``--json-output`` so that ``ai-readiness-finalize``
    can reconstruct a full plan after Claude provides L2 verdicts inline.
    """
    readiness = compute_readiness(project_dir, preset, session_id=session_id)
    cache = diagnose_cache_for_project(project_dir, model=model)
    return {
        "readiness": readiness.model_dump(),
        "cache": cache.model_dump(),
        "preset": preset.value,
    }


def run_structural(
    project_dir: Path,
    *,
    preset: Preset,
    model: str = "claude-sonnet-4-6",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Compute the ``structural`` field for the /hm:health dashboard (0.13.0).

    Returns ``{"score": <0-100 int>, "signals_failed": [...]}``. The
    score is the weighted blend of the deterministic L1 readiness signals
    (70%) and the L3 cache-diagnostic score (5% in the legacy weighting —
    surfaced here as a small additive component so a degenerate cache
    state can still pull the structural score down). L2 is intentionally
    NOT folded into ``structural``: the LLM-judged content score belongs
    to a different concern and the verify-stage Check 3 contract names
    "structural" specifically.

    Key rename (0.13.1, PLAN-health-plugin-bugs-2026-05 ADR-001): the
    inner score key was renamed from ``"structural"`` to ``"score"`` so
    the schema is no longer nested under the same name as the outer
    section. The dashboard renderer and its unit tests have always read
    ``.get("score")`` — pre-0.13.1 the producer drifted to ``"structural"``
    silently, causing every rendered dashboard to show ``score: 0 / 100``.

    ``signals_failed`` is the flat list of ``layer1:<signal_id>`` entries
    whose ``passed`` flag is False — one line per failed deterministic
    check so the dashboard reader can show a count without re-running the
    layer.
    """
    readiness = compute_readiness(project_dir, preset, session_id=session_id)
    cache = diagnose_cache_for_project(project_dir, model=model)

    # Blend: 70% readiness (deterministic structural) + 5% cache; the
    # remaining 25% slot belongs to L2 (llm_judge) which lives in a
    # separate field of the dashboard once the templates land in Phase 2.
    # Until then we treat L2 as neutral 50 so the structural number remains
    # comparable to the pre-0.13.0 single-score dashboard for users mid-
    # migration. Renormalize after dropping L2 so the result is in [0, 100].
    weighted = (readiness.composite * 0.70 + cache.score * 0.05) / 0.75
    structural_score = max(0, min(100, round(weighted)))

    signals_failed: list[str] = []
    for dim_name, dim in readiness.dimensions.items():
        for sig in dim.signals:
            if not sig.passed:
                signals_failed.append(f"{dim_name}:{sig.id}")

    # PLAN-antisycophancy-2026-05 ADR-006: communication-protocol sub-check.
    # Discovers dispatcher templates + 5 pinned LLM-judgment skills, requires
    # `communication_variant` frontmatter on each, and verifies the rendered
    # marker matches source. Silent-miss (the R4 WRONG-probe failure mode)
    # surfaces here as structured ActionItem records; the /hm:health
    # accept/reject/defer loop walks them unchanged (0.13.0 ADR-001).
    templates_root = Path(__file__).resolve().parent / "templates"
    output_root = project_dir / ".claude"
    comm_items = audit_communication(
        templates_root, output_dir=output_root if output_root.is_dir() else None
    )
    for item in comm_items:
        signals_failed.append(f"communication_protocol:{item.target}")

    return {
        "score": structural_score,
        "signals_failed": signals_failed,
        "communication_items": [it.model_dump() for it in comm_items],
    }


def finalize_from_verdicts_json(
    scores_path: Path,
    verdicts_path: Path,
) -> ImprovementPlan:
    """Reconstruct a full ImprovementPlan from pre-computed L1+L3 + Claude L2 verdicts.

    ``verdicts_path`` must contain a JSON array of objects in the form:
    ``[{"file": "...", "dimension": "...", "verdicts": [{...RubricVerdict fields...}]}]``

    The ``score`` field is computed from the verdicts; ``error`` defaults to null.
    """
    try:
        scores = json.loads(scores_path.read_text(encoding="utf-8"))
        readiness = ReadinessResult.model_validate(scores["readiness"])
        cache = CacheDiagnosis.model_validate(scores["cache"])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        msg = f"Could not parse scores JSON at {scores_path}: {e}"
        raise ValueError(msg) from e

    try:
        raw_verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        msg = f"Could not parse verdicts JSON at {verdicts_path}: {e}"
        raise ValueError(msg) from e
    judge_results: list[JudgeResult] = []
    if isinstance(raw_verdicts, list):
        for entry in raw_verdicts:
            if not isinstance(entry, dict):
                continue
            verdicts = [
                RubricVerdict.model_validate(v)
                for v in entry.get("verdicts", [])
                if isinstance(v, dict)
            ]
            score = compute_score_from_verdicts(verdicts) if verdicts else 50
            judge_results.append(
                JudgeResult(
                    file=str(entry.get("file", "")),
                    dimension=str(entry.get("dimension", "")),
                    score=score,
                    verdicts=verdicts,
                    error=entry.get("error"),
                )
            )

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
    footer = _deferred_items_footer(plan)
    if not plan.actions:
        if footer:
            lines.append(footer)
        else:
            lines.append("No actions — project looks healthy.")
        return "\n".join(lines)

    lines.append(f"Top {min(max_actions, len(plan.actions))} of {len(plan.actions)} actions:")
    for a in plan.actions[:max_actions]:
        lines.append(f"  [{a.priority}] {a.dimension} :: {a.summary}")
        lines.append(f"        → {a.suggestion}")
    if len(plan.actions) > max_actions:
        lines.append(f"  … {len(plan.actions) - max_actions} more (run --verbose for full list)")
    if footer:
        lines.append(footer)
    return "\n".join(lines)


def _deferred_items_footer(plan: ImprovementPlan) -> str:
    """One-line note explaining the deferred/demoted items (ADR-004).

    Empty string when neither category is active so callers can branch.
    """
    pieces: list[str] = []
    if plan.deferred_telemetry > 0:
        pieces.append(
            f"{plan.deferred_telemetry} telemetry signal(s) auto-populate after ≥ 5 turns"
        )
    if plan.demoted_governance > 0:
        pieces.append(f"{plan.demoted_governance} aspirational governance item(s) demoted to P2")
    if not pieces:
        return ""
    total = plan.deferred_telemetry + plan.demoted_governance
    return f"  … {total} item(s) deferred ({'; '.join(pieces)}). Run /hm:health for full list."


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
        f"| llm_judge | {plan.layer_scores['llm_judge']} | LLM-judged content quality vs rubrics |",
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
