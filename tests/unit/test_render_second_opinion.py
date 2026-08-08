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
    assert "Bash(agy --sandbox --print:*)" in settings


def test_codex_only_no_agy_allow(tmp_path: Path) -> None:
    root = _render(["codex"], tmp_path)
    settings = (root / "settings.json").read_text()
    assert "Bash(codex exec:*)" in settings
    assert "Bash(agy --sandbox --print:*)" not in settings


def test_antigravity_only_no_codex_allow(tmp_path: Path) -> None:
    root = _render(["antigravity"], tmp_path)
    settings = (root / "settings.json").read_text()
    assert "Bash(agy --sandbox --print:*)" in settings
    assert "Bash(codex exec:*)" not in settings


def test_disabled_is_byte_zero_second_opinion(tmp_path: Path) -> None:
    root = _render([], tmp_path)
    settings = (root / "settings.json").read_text()
    assert "Bash(agy --sandbox --print:*)" not in settings
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
    # Both recipes now call the invoker, which owns argv construction. The old rendered
    # `agy --print --sandbox …` shape was never a working command — `--print` takes the
    # prompt as its VALUE, so `--sandbox` became the prompt and stdin was never read.
    assert "hm second_opinion_invoke --model antigravity" in review
    assert "hm second_opinion_invoke --model codex" in review
    assert "agy --print --sandbox --print-timeout" not in review
    assert "timeout 240 agy" not in review  # NOT the external-timeout wrapper either


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
    # ADR-005: the smoke calls the SAME entrypoint as the stage recipe. The previous
    # smoke was a hand-copied duplicate of the raw CLI line, and it drifted from the
    # original in the one dimension that mattered — it ran at the base, where a
    # cwd-relative schema path resolves — so it reported green against a dead vote.
    assert "second_opinion_invoke --model antigravity --smoke" in health
    assert "--stage health" in health
    assert "agy --print --sandbox" not in health


def test_custom_antigravity_model_is_persisted_for_the_invoker(tmp_path: Path) -> None:
    """The configured model reaches the CLI through harness.yaml, not through the recipe.

    It used to be inlined as `--model "<value>"` in the rendered prose. Now the invoker
    reads it from the BASE repo's harness.yaml at call time — which is what lets it
    survive a worktree cwd that has no `.claude/` at all. So the render-side contract is
    "the value is persisted", and `test_config_survives_a_worktree_cwd_with_no_claude_dir`
    owns the other half: that the persisted value actually reaches the argv.
    """
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

    harness_yaml = (tmp_path / "harness.yaml").read_text()
    assert "Gemini 3.5 Flash (High)" in harness_yaml
    review = (tmp_path / "commands/hm/review.md").read_text()
    assert "second_opinion_invoke --model antigravity" in review


def test_fresh_install_harness_yaml_pins_the_flash_default(tmp_path: Path) -> None:
    """The ABSENT case: no `second_opinion` block at all — the fresh-install path.

    Absent-case coverage per CLAUDE.md's `[fail:design]` rule (count:8): every other
    test in this file passes an EXPLICIT `SecondOpinionConfig`, so none of them covers
    what a brand-new harness actually gets.

    Note what this test established, against ADR-003's original reasoning: the two
    `harness-yaml/*.yaml.j2` literals are NOT the fresh-install path. `second_opinion`
    is a non-Optional field with a default, so `config.second_opinion` is never falsy on
    a synthesized blueprint and those `else` branches are unreachable. A fresh install
    inherits the Python default in `models.py`. The template literals were still worth
    correcting — a stale literal is a documentation lie that the next reader will trust —
    but they were never load-bearing, and this test asserts the path that IS.
    """
    ans = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE],
    )
    assert ans.second_opinion.antigravity.model == "Gemini 3.6 Flash (High)", (
        "the default-constructed config is the fresh-install path"
    )

    bp = synthesize(ProjectProfile(), ans)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    harness_yaml = (tmp_path / "harness.yaml").read_text()
    assert "Gemini 3.6 Flash (High)" in harness_yaml
    assert "Gemini 3.1 Pro (High)" not in harness_yaml
