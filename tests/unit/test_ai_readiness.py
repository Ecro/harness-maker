"""Orchestrator tests — combine readiness + judge + cache → plan + renders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.ai_readiness import (
    finalize_from_verdicts_json,
    render_dashboard_markdown,
    render_terminal_summary,
    run_ai_readiness,
    run_ai_readiness_structural,
)
from harness_maker.llm_judge import JudgeClient
from harness_maker.models import Preset


class _FakeJudgeClient:
    """Returns the same all-passed JSON for any rubric."""

    def __init__(self, all_pass: bool = True) -> None:
        self.all_pass = all_pass
        self.calls: list[dict[str, Any]] = []

    def judge(self, system: str, user: str, model: str) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        # Best-effort: extract rubric IDs from the system prompt to construct
        # a matching response. The system prompt embeds "id: <rid>" lines.
        verdicts = []
        for line in system.splitlines():
            stripped = line.strip()
            if stripped.startswith("- id: "):
                rid = stripped.removeprefix("- id: ").strip()
                verdicts.append(
                    {
                        "rubric_id": rid,
                        "passed": self.all_pass,
                        "evidence": "stub",
                        "suggestion": None if self.all_pass else "stub fix",
                    }
                )
        return json.dumps({"verdicts": verdicts})


def _seed_minimal_project(tmp_path: Path) -> Path:
    (tmp_path / "CLAUDE.md").write_text("# project\nstack: python\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# readme\n", encoding="utf-8")
    return tmp_path


# ── run_ai_readiness ───────────────────────────────────────────────────────


def test_run_no_rubrics_no_llm(tmp_path: Path) -> None:
    """Empty project, no rubrics, skip_llm — only Layers 1 + 3 contribute."""
    _seed_minimal_project(tmp_path)
    plan = run_ai_readiness(tmp_path, preset=Preset.SIDE, skip_llm=True)
    assert plan.layer_scores["llm_judge"] == 50  # neutral, no L2 ran
    assert plan.layer_scores["cache"] == 50  # no metrics.jsonl
    assert 0 <= plan.composite_score <= 100


def test_run_with_fake_client_and_rubrics(tmp_path: Path) -> None:
    """Rubric YAMLs present + fake client → L2 contributes to composite."""
    _seed_minimal_project(tmp_path)
    rubrics_dir = tmp_path / ".claude" / "rubrics"
    rubrics_dir.mkdir(parents=True)
    (rubrics_dir / "claude_md.yaml").write_text(
        """\
dimension: context_quality
target: CLAUDE.md
rubrics:
  - id: stack_specified
    description: tech stack documented?
    severity: P0
    action: add stack
  - id: build_documented
    description: build commands documented?
    severity: P1
    action: add commands
""",
        encoding="utf-8",
    )
    fake = _FakeJudgeClient(all_pass=True)
    plan = run_ai_readiness(tmp_path, preset=Preset.SIDE, judge_client=fake)
    assert plan.layer_scores["llm_judge"] == 100
    assert len(fake.calls) == 1  # one file (CLAUDE.md) judged once


def test_run_skip_llm_short_circuits_judge(tmp_path: Path) -> None:
    """skip_llm=True must NOT call the judge client even when rubrics present."""
    _seed_minimal_project(tmp_path)
    rubrics_dir = tmp_path / ".claude" / "rubrics"
    rubrics_dir.mkdir(parents=True)
    (rubrics_dir / "claude_md.yaml").write_text(
        """\
dimension: context_quality
target: CLAUDE.md
rubrics:
  - id: x
    description: x
    severity: P0
    action: x
""",
        encoding="utf-8",
    )
    fake = _FakeJudgeClient()
    plan = run_ai_readiness(tmp_path, preset=Preset.SIDE, skip_llm=True, judge_client=fake)
    assert fake.calls == []
    assert plan.layer_scores["llm_judge"] == 50


def test_run_handles_anthropic_client_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If AnthropicJudgeClient raises (no API key), Layer 2 is skipped silently."""
    _seed_minimal_project(tmp_path)
    rubrics_dir = tmp_path / ".claude" / "rubrics"
    rubrics_dir.mkdir(parents=True)
    (rubrics_dir / "x.yaml").write_text(
        "dimension: context_quality\n"
        "target: CLAUDE.md\n"
        "rubrics:\n"
        "  - id: x\n"
        "    description: x\n"
        "    severity: P0\n"
        "    action: x\n",
        encoding="utf-8",
    )

    def _raise(*_a: Any, **_kw: Any) -> None:
        raise RuntimeError("no api key")

    monkeypatch.setattr("harness_maker.ai_readiness.AnthropicJudgeClient", _raise)
    plan = run_ai_readiness(tmp_path, preset=Preset.SIDE)
    assert plan.layer_scores["llm_judge"] == 50  # neutral when L2 blocked


def test_run_uses_metrics_for_cache_layer(tmp_path: Path) -> None:
    """A populated metrics.jsonl drives the cache score above neutral."""
    _seed_minimal_project(tmp_path)
    obs = tmp_path / ".claude" / "observability"
    obs.mkdir(parents=True)
    entries = [
        {
            "timestamp": f"2026-05-01T00:0{i}:00+00:00",
            "input_tokens": 100,
            "cache_read_tokens": 5000,
            "cache_creation_tokens": 0,
        }
        for i in range(10)
    ]
    (obs / "metrics.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )
    plan = run_ai_readiness(tmp_path, preset=Preset.SIDE, skip_llm=True)
    assert plan.layer_scores["cache"] == 100


# ── render_terminal_summary ────────────────────────────────────────────────


def test_terminal_summary_includes_score_and_layers(tmp_path: Path) -> None:
    plan = run_ai_readiness(tmp_path, preset=Preset.SIDE, skip_llm=True)
    text = render_terminal_summary(plan)
    assert "ai-readiness:" in text
    assert "Layer scores:" in text
    assert "readiness" in text
    assert "llm_judge" in text
    assert "cache" in text


def test_terminal_summary_caps_actions(tmp_path: Path) -> None:
    plan = run_ai_readiness(tmp_path, preset=Preset.SIDE, skip_llm=True)
    text = render_terminal_summary(plan, max_actions=3)
    if len(plan.actions) > 3:
        assert "more" in text


def test_terminal_summary_healthy_project(tmp_path: Path) -> None:
    """When there are no actions, the summary explicitly says so."""
    from harness_maker.improvement import ImprovementPlan

    plan = ImprovementPlan(
        composite_score=95,
        layer_scores={"readiness": 95, "llm_judge": 95, "cache": 100},
        actions=[],
    )
    assert "looks healthy" in render_terminal_summary(plan)


# ── render_dashboard_markdown ──────────────────────────────────────────────


def test_dashboard_markdown_has_table_when_actions_present(tmp_path: Path) -> None:
    plan = run_ai_readiness(tmp_path, preset=Preset.SIDE, skip_llm=True)
    md = render_dashboard_markdown(plan, "test-proj")
    assert "# AI Readiness — test-proj" in md
    assert "| Layer | Score |" in md
    if plan.actions:
        assert "| Priority | Dimension | Summary | Suggestion |" in md


def test_dashboard_markdown_handles_pipe_in_text() -> None:
    """Pipe characters in evidence/suggestion must be escaped for markdown tables."""
    from harness_maker.improvement import ActionItem, ImprovementPlan

    plan = ImprovementPlan(
        composite_score=50,
        layer_scores={"readiness": 50, "llm_judge": 50, "cache": 50},
        actions=[
            ActionItem(
                priority="P0",
                dimension="context_quality",
                target="CLAUDE.md",
                summary="missing | section",
                detail="evidence | with | pipes",
                suggestion="run rm | xargs grep",
                source="layer1:test",
            ),
        ],
    )
    md = render_dashboard_markdown(plan, "x")
    # Body of suggestion appears with escaped pipes (rendered string contains `\|`)
    assert "rm \\| xargs" in md


# ── structural + finalize path ─────────────────────────────────────────────


def test_run_ai_readiness_structural_returns_json_serializable(tmp_path: Path) -> None:
    """run_ai_readiness_structural output is dict with 'readiness' and 'cache' keys."""
    import json

    result = run_ai_readiness_structural(tmp_path, preset=Preset.SIDE)
    assert "readiness" in result
    assert "cache" in result
    assert "preset" in result
    # Must be JSON-serializable (no pydantic objects)
    json.dumps(result)  # raises if not serializable


def test_finalize_from_verdicts_json_round_trip(tmp_path: Path) -> None:
    """finalize_from_verdicts_json reconstructs a plan from JSON files."""
    import json

    scores = run_ai_readiness_structural(tmp_path, preset=Preset.SIDE)
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps(scores), encoding="utf-8")

    # Claude provides these verdicts (one passing, one failing)
    verdicts = [
        {
            "file": str(tmp_path / "CLAUDE.md"),
            "dimension": "context_quality",
            "verdicts": [
                {
                    "rubric_id": "has_overview",
                    "severity": "P0",
                    "passed": True,
                    "evidence": "Overview section found at line 1",
                    "suggestion": None,
                },
                {
                    "rubric_id": "has_examples",
                    "severity": "P1",
                    "passed": False,
                    "evidence": "No examples section found",
                    "suggestion": "Add a ## Examples section",
                },
            ],
        }
    ]
    verdicts_path = tmp_path / "verdicts.json"
    verdicts_path.write_text(json.dumps(verdicts), encoding="utf-8")

    plan = finalize_from_verdicts_json(scores_path, verdicts_path)
    # L2 ran → score is not the neutral 50
    assert plan.layer_scores["llm_judge"] != 50
    # The failing rubric item appears as an action
    action_sources = [a.source for a in plan.actions]
    assert any("has_examples" in s for s in action_sources)


def test_finalize_from_verdicts_json_empty_verdicts(tmp_path: Path) -> None:
    """Empty verdicts list → L2 neutral (50)."""
    import json

    scores = run_ai_readiness_structural(tmp_path, preset=Preset.SIDE)
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps(scores), encoding="utf-8")
    verdicts_path = tmp_path / "verdicts.json"
    verdicts_path.write_text("[]", encoding="utf-8")

    plan = finalize_from_verdicts_json(scores_path, verdicts_path)
    assert plan.layer_scores["llm_judge"] == 50


def test_dashboard_markdown_no_actions_message() -> None:
    from harness_maker.improvement import ImprovementPlan

    plan = ImprovementPlan(
        composite_score=100,
        layer_scores={"readiness": 100, "llm_judge": 100, "cache": 100},
        actions=[],
    )
    md = render_dashboard_markdown(plan, "x")
    assert "(none — project looks healthy)" in md


def test_finalize_from_verdicts_json_malformed_scores_raises(tmp_path: Path) -> None:
    """Malformed scores JSON raises ValueError, not a raw KeyError/JSONDecodeError."""

    scores_path = tmp_path / "scores.json"
    scores_path.write_text('{"not_readiness": {}}', encoding="utf-8")
    verdicts_path = tmp_path / "verdicts.json"
    verdicts_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="scores JSON"):
        finalize_from_verdicts_json(scores_path, verdicts_path)


def test_judge_client_protocol_satisfied_by_fake() -> None:
    fake: JudgeClient = _FakeJudgeClient()
    assert callable(getattr(fake, "judge", None))
