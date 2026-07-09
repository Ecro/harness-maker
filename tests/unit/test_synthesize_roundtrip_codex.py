"""Phase 3 — harness.yaml round-trip for the second_opinion block.

PLAN-second-opinion-multi-model ADR-001/002: the block was renamed from the
single-vendor `codex_second_opinion` (`enabled: bool`) to the multi-vendor
`second_opinion` (`models: list[str]`), matching the feedback/second_brain
unconditional-emit pattern. Legacy harness.yaml files carrying the old
`codex_second_opinion` block (and no `second_opinion` key) migrate via
`_load_second_opinion`: `enabled: true` -> `models=["codex"]`.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import (
    InterviewAnswers,
    Preset,
    ProjectProfile,
    SecondOpinionConfig,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _build_answers(*, models: list[str]) -> InterviewAnswers:
    return InterviewAnswers(
        preset=Preset.SIDE,
        targets=[Target.CLAUDE_CODE],
        second_opinion=SecondOpinionConfig(models=models),  # type: ignore[arg-type]
    )


def test_legacy_yaml_without_key_loads_with_default(tmp_path: Path) -> None:
    """harness.yaml missing the key loads with default (models=[], disabled)."""
    legacy_yaml = """\
---
generated_by: harness-maker
---
preset: Side
locale: en
targets: [claude-code]
default_workflow: exec-rev-wrap
fused_workflows:
  exec-rev-wrap: [execute, review, wrapup]
"""
    p = tmp_path / "harness.yaml"
    p.write_text(legacy_yaml)
    answers = answers_from_harness_yaml(p)
    assert answers is not None
    assert answers.second_opinion.enabled is False
    assert answers.second_opinion.models == []
    assert answers.second_opinion.agents == [
        "code-reviewer",
        "consensus-arbiter",
        "plan-validator",
    ]


def test_legacy_codex_second_opinion_block_migrates_to_second_opinion(tmp_path: Path) -> None:
    """A legacy `codex_second_opinion: {enabled: true}` block (no `second_opinion`
    key present) migrates to `second_opinion.models == ["codex"]` (ADR-001)."""
    legacy_yaml = """\
---
generated_by: harness-maker
---
preset: Side
locale: en
targets: [claude-code]
default_workflow: exec-rev-wrap
fused_workflows:
  exec-rev-wrap: [execute, review, wrapup]
codex_second_opinion:
  enabled: true
"""
    p = tmp_path / "harness.yaml"
    p.write_text(legacy_yaml)
    answers = answers_from_harness_yaml(p)
    assert answers is not None
    assert answers.second_opinion.enabled is True
    assert answers.second_opinion.models == ["codex"]


def test_yaml_with_block_round_trips(tmp_path: Path) -> None:
    """Render -> load -> re-render produces a stable second_opinion block.

    models=["codex"] forward emit is read back as models=["codex"]; the field
    survives the synthesize -> render -> answers_from_harness_yaml cycle.
    """
    answers_in = _build_answers(models=["codex"])
    bp = synthesize(ProjectProfile(), answers_in)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    yaml_path = tmp_path / "harness.yaml"
    assert yaml_path.exists()
    body = yaml_path.read_text()
    # Forward emit MUST include the block (matches feedback/second_brain pattern).
    assert "second_opinion:" in body, "harness.yaml missing second_opinion block"
    assert 'models: ["codex"]' in body
    # The legacy single-vendor key must no longer be emitted.
    assert "codex_second_opinion:" not in body
    # Reverse round-trip preserves models=["codex"].
    restored = answers_from_harness_yaml(yaml_path)
    assert restored is not None
    assert restored.second_opinion.enabled is True
    assert restored.second_opinion.models == ["codex"]


def test_disabled_yaml_emits_block_with_empty_models(tmp_path: Path) -> None:
    """Forward writer emits the block even when disabled (matches
    existing pattern for second_brain/feedback — unconditional emit)."""
    answers_in = _build_answers(models=[])
    bp = synthesize(ProjectProfile(), answers_in)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    body = (tmp_path / "harness.yaml").read_text()
    assert "second_opinion:" in body, (
        "harness.yaml must emit second_opinion block unconditionally (ADR-005 P-W2)"
    )
    assert "models: []" in body


def test_multi_model_yaml_round_trips(tmp_path: Path) -> None:
    """Both models enabled together survive the round trip (ADR-002: independent
    per-vendor selection, both-at-once allowed)."""
    answers_in = _build_answers(models=["codex", "antigravity"])
    bp = synthesize(ProjectProfile(), answers_in)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    yaml_path = tmp_path / "harness.yaml"
    body = yaml_path.read_text()
    assert 'models: ["codex", "antigravity"]' in body
    restored = answers_from_harness_yaml(yaml_path)
    assert restored is not None
    assert restored.second_opinion.models == ["codex", "antigravity"]
