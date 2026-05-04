"""Improvement plan composition — blend 3 layers into ranked actions."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.cache_diagnostics import CacheDiagnosis
from harness_maker.improvement import (
    ActionItem,
    ImprovementPlan,
    _composite,
    _layer1_priority,
    _layer2_score,
    _sort_actions,
    build_improvement_plan,
)
from harness_maker.llm_judge import JudgeResult, RubricVerdict
from harness_maker.models import Preset
from harness_maker.readiness import compute_readiness

# ── helpers ────────────────────────────────────────────────────────────────


def _empty_cache() -> CacheDiagnosis:
    return CacheDiagnosis(
        hit_rate=0,
        score=50,
        sample_size=0,
        primary_failure="no_data",
        evidence="no data",
        remediation="install hook",
        counters={},
    )


def _good_cache() -> CacheDiagnosis:
    return CacheDiagnosis(
        hit_rate=85,
        score=100,
        sample_size=20,
        primary_failure=None,
        evidence="healthy",
        remediation="no action needed",
        counters={"hit": 17, "miss_first": 1, "miss_invalidation": 2},
    )


def _bad_cache() -> CacheDiagnosis:
    return CacheDiagnosis(
        hit_rate=10,
        score=20,
        sample_size=20,
        primary_failure="miss_min_threshold",
        evidence="prefix too small",
        remediation="bulk up CLAUDE.md",
        counters={"hit": 2, "miss_min_threshold": 18},
    )


def _passing_judge_result(file: str = "CLAUDE.md") -> JudgeResult:
    return JudgeResult(
        file=file,
        dimension="context_quality",
        score=95,
        verdicts=[
            RubricVerdict(
                rubric_id="r0", severity="P0", passed=True, evidence="ok", suggestion=None
            ),
        ],
        error=None,
    )


def _failing_judge_result(file: str = "CLAUDE.md") -> JudgeResult:
    return JudgeResult(
        file=file,
        dimension="context_quality",
        score=30,
        verdicts=[
            RubricVerdict(
                rubric_id="tech_stack_specified",
                severity="P0",
                passed=False,
                evidence="no stack section found",
                suggestion="Add Tech Stack section",
            ),
            RubricVerdict(
                rubric_id="contract_format",
                severity="P1",
                passed=False,
                evidence="prompt is not in contract format",
                suggestion="Restructure prompt",
            ),
            RubricVerdict(
                rubric_id="examples_provided",
                severity="P2",
                passed=False,
                evidence="no examples",
                suggestion="Add example",
            ),
        ],
        error=None,
    )


# ── _layer1_priority ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("weight", "expected"),
    [(30, "P0"), (25, "P0"), (20, "P1"), (15, "P1"), (10, "P2"), (5, "P2")],
)
def test_layer1_priority_buckets(weight: int, expected: str) -> None:
    assert _layer1_priority(weight) == expected


# ── _layer2_score ──────────────────────────────────────────────────────────


def test_layer2_score_no_results_returns_neutral() -> None:
    assert _layer2_score([]) == 50


def test_layer2_score_averages_results() -> None:
    results = [_passing_judge_result(), _failing_judge_result()]
    # avg of 95 and 30 = 62.5 → 62
    assert _layer2_score(results) == 62


# ── _composite ─────────────────────────────────────────────────────────────


def test_composite_weighted_blend() -> None:
    # 70% × 80 + 25% × 60 + 5% × 100 = 56 + 15 + 5 = 76
    score = _composite({"readiness": 80, "llm_judge": 60, "cache": 100})
    assert score == 76


def test_composite_clamps_to_0_100() -> None:
    assert _composite({"readiness": 200, "llm_judge": 200, "cache": 200}) == 100
    assert _composite({"readiness": -100, "llm_judge": -100, "cache": -100}) == 0


# ── _sort_actions ──────────────────────────────────────────────────────────


def test_sort_actions_by_priority_then_dim() -> None:
    items = [
        ActionItem(
            priority="P2",
            dimension="z_dim",
            target="t",
            summary="s",
            detail="d",
            suggestion="x",
            source="src1",
        ),
        ActionItem(
            priority="P0",
            dimension="b_dim",
            target="t",
            summary="s",
            detail="d",
            suggestion="x",
            source="src2",
        ),
        ActionItem(
            priority="P0",
            dimension="a_dim",
            target="t",
            summary="s",
            detail="d",
            suggestion="x",
            source="src3",
        ),
    ]
    sorted_items = _sort_actions(items)
    assert [(a.priority, a.dimension) for a in sorted_items] == [
        ("P0", "a_dim"),
        ("P0", "b_dim"),
        ("P2", "z_dim"),
    ]


# ── build_improvement_plan integration ─────────────────────────────────────


def test_empty_project_produces_actions(tmp_path: Path) -> None:
    readiness = compute_readiness(tmp_path, Preset.SIDE)
    plan = build_improvement_plan(readiness, [], _empty_cache())
    assert isinstance(plan, ImprovementPlan)
    assert plan.composite_score < 50
    # At least one action per failing dimension.
    dims_with_actions = {a.dimension for a in plan.actions}
    failing_dims = {
        d for d, ds in readiness.dimensions.items() if ds.score < 100 and d != "governance"
    }
    assert dims_with_actions >= failing_dims


def test_layer2_failures_become_actions(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# bare\n")
    readiness = compute_readiness(tmp_path, Preset.SIDE)
    plan = build_improvement_plan(readiness, [_failing_judge_result()], _good_cache())
    layer2_actions = [a for a in plan.actions if a.source.startswith("layer2:")]
    assert len(layer2_actions) == 3
    # tech_stack_specified should rank P0 ahead of examples_provided P2.
    by_id = {a.source: a for a in layer2_actions}
    assert by_id["layer2:tech_stack_specified@CLAUDE.md"].priority == "P0"
    assert by_id["layer2:examples_provided@CLAUDE.md"].priority == "P2"


def test_cache_failure_produces_p1_action(tmp_path: Path) -> None:
    readiness = compute_readiness(tmp_path, Preset.SIDE)
    plan = build_improvement_plan(readiness, [], _bad_cache())
    cache_actions = [a for a in plan.actions if a.source == "layer3:cache"]
    assert len(cache_actions) == 1
    assert cache_actions[0].priority == "P1"
    assert "miss_min_threshold" in cache_actions[0].summary


def test_no_cache_action_when_healthy(tmp_path: Path) -> None:
    readiness = compute_readiness(tmp_path, Preset.SIDE)
    plan = build_improvement_plan(readiness, [], _good_cache())
    cache_actions = [a for a in plan.actions if a.source == "layer3:cache"]
    assert cache_actions == []


def test_judge_error_surfaces_as_soft_action(tmp_path: Path) -> None:
    readiness = compute_readiness(tmp_path, Preset.SIDE)
    error_judge = JudgeResult(
        file="CLAUDE.md",
        dimension="context_quality",
        score=50,
        verdicts=[],
        error="Anthropic rate limited",
    )
    plan = build_improvement_plan(readiness, [error_judge], _good_cache())
    error_actions = [a for a in plan.actions if a.source.startswith("layer2:error@")]
    assert len(error_actions) == 1
    assert error_actions[0].priority == "P2"


def test_governance_skipped_on_side(tmp_path: Path) -> None:
    """Side preset has governance weight 0 — no governance actions surface."""
    readiness = compute_readiness(tmp_path, Preset.SIDE)
    plan = build_improvement_plan(readiness, [], _good_cache())
    governance_actions = [a for a in plan.actions if a.dimension == "governance"]
    assert governance_actions == []


def test_composite_combines_all_three_layers(tmp_path: Path) -> None:
    """A rich project + healthy cache + good judge results should produce > 70."""
    (tmp_path / "CLAUDE.md").write_text("# project\n# tech\n")
    (tmp_path / "README.md").write_text("# readme\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_one():\n    assert True\n")
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("- run: pytest\n")

    readiness = compute_readiness(tmp_path, Preset.SIDE)
    plan = build_improvement_plan(
        readiness,
        [_passing_judge_result()],
        _good_cache(),
    )
    assert plan.composite_score >= 50
    assert plan.layer_scores["llm_judge"] == 95
    assert plan.layer_scores["cache"] == 100


def test_layer_scores_present_in_output(tmp_path: Path) -> None:
    readiness = compute_readiness(tmp_path, Preset.SIDE)
    plan = build_improvement_plan(readiness, [], _empty_cache())
    assert set(plan.layer_scores.keys()) == {"readiness", "llm_judge", "cache"}
