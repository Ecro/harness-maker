"""Render-side contract for multi-model second opinion (PLAN-second-opinion-multi-model).

Covers: per-model Bash allow-lines + bare-Bash availability, nested harness.yaml shape,
schema gating, byte-zero disabled render, and the ADR-007 render-determinism invariant
(render never shells out to `agy`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker.models import (
    InterviewAnswers,
    Preset,
    ProjectProfile,
    SecondOpinionAntigravityConfig,
    SecondOpinionConfig,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render(models: list[str], tmp_path: Path, preset: Preset = Preset.PRODUCTION) -> Path:
    ans = InterviewAnswers(
        preset=preset,
        targets=[Target.CLAUDE_CODE],
        second_opinion=SecondOpinionConfig(models=models),  # type: ignore[arg-type]
    )
    bp = synthesize(ProjectProfile(), ans)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def test_both_models_render_both_allow_lines(tmp_path: Path) -> None:
    root = _render(["codex", "antigravity"], tmp_path)
    settings = (root / "settings.json").read_text()
    assert "Bash(codex exec:*)" in settings
    assert "Bash(agy --print --sandbox:*)" in settings


def test_codex_only_no_agy_allow(tmp_path: Path) -> None:
    root = _render(["codex"], tmp_path)
    settings = (root / "settings.json").read_text()
    assert "Bash(codex exec:*)" in settings
    assert "Bash(agy --print --sandbox:*)" not in settings


def test_antigravity_only_no_codex_allow(tmp_path: Path) -> None:
    root = _render(["antigravity"], tmp_path)
    settings = (root / "settings.json").read_text()
    assert "Bash(agy --print --sandbox:*)" in settings
    assert "Bash(codex exec:*)" not in settings


def test_disabled_is_byte_zero_second_opinion(tmp_path: Path) -> None:
    root = _render([], tmp_path)
    settings = (root / "settings.json").read_text()
    assert "Bash(agy --print --sandbox:*)" not in settings
    assert "Bash(codex exec:*)" not in settings
    review = (root / "commands/hm/review.md").read_text()
    plan = (root / "commands/hm/plan.md").read_text()
    assert "Cross-model heterogeneous" not in review
    assert "second_opinion_results" not in plan
    assert not (root / "schemas/second-opinion-finding.schema.json").exists()


def test_nested_harness_yaml_shape(tmp_path: Path) -> None:
    root = _render(["codex", "antigravity"], tmp_path)
    hy = (root / "harness.yaml").read_text()
    assert "second_opinion:" in hy
    assert 'models: ["codex", "antigravity"]' in hy
    assert "codex:" in hy
    assert "antigravity:" in hy
    assert "codex_second_opinion:" not in hy


def test_schema_rendered_when_enabled(tmp_path: Path) -> None:
    root = _render(["antigravity"], tmp_path)
    assert (root / "schemas/second-opinion-finding.schema.json").exists()


def test_dispatch_partial_loops_both_models_in_review(tmp_path: Path) -> None:
    root = _render(["codex", "antigravity"], tmp_path)
    review = (root / "commands/hm/review.md").read_text()
    assert "model: `codex`" in review
    assert "model: `antigravity`" in review
    # antigravity recipe must use agy's native --print-timeout (Phase-1 hang guard) and begin
    # with `agy` so the scoped Bash(agy --print --sandbox:*) allow rule prefix-matches it (review)
    assert "agy --print --sandbox --print-timeout 120s" in review
    assert "timeout 120 agy" not in review  # NOT the external-timeout wrapper (allow-rule miss)


def test_plan_uses_second_opinion_results_contract(tmp_path: Path) -> None:
    root = _render(["codex"], tmp_path)
    plan = (root / "commands/hm/plan.md").read_text()
    assert "second_opinion_results" in plan
    assert "codex_status" not in plan
    assert "codex_reconciliation" not in plan


def test_render_never_shells_out_to_agy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ADR-007 determinism invariant: render must read the persisted model value, never
    invoke `agy` — a render-time shell-out would make snapshot output machine-dependent."""
    calls: list[list[str]] = []
    real_run = subprocess.run

    def _spy(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        argv = args[0] if args else kwargs.get("args")
        if isinstance(argv, (list, tuple)) and argv and argv[0] == "agy":
            calls.append(list(argv))
        return real_run(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(subprocess, "run", _spy)
    _render(["antigravity"], tmp_path)
    assert calls == [], f"render shelled out to agy: {calls}"


def test_health_smoke_has_antigravity_block(tmp_path: Path) -> None:
    root = _render(["antigravity"], tmp_path)
    health = (root / "commands/hm/health.md").read_text()
    assert "agy --print --sandbox --print-timeout 120s" in health
    assert "adapt --model antigravity" in health


def test_custom_antigravity_model_flows_to_recipe(tmp_path: Path) -> None:
    ans = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE],
        second_opinion=SecondOpinionConfig(
            models=["antigravity"],
            antigravity=SecondOpinionAntigravityConfig(model="Gemini 3.5 Flash (High)"),
        ),
    )
    bp = synthesize(ProjectProfile(), ans)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    review = (tmp_path / "commands/hm/review.md").read_text()
    assert '--model "Gemini 3.5 Flash (High)"' in review
