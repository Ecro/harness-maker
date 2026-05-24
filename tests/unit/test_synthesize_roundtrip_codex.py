"""Phase 3 — harness.yaml round-trip for codex_second_opinion block.

PLAN-codex-second-llm-integration ADR-005 P-W2: forward writer emits the
block UNCONDITIONALLY (matches feedback/second_brain pattern). Legacy
harness.yaml files without the key load with the default-factory default
(enabled=False) so existing user configs don't break on upgrade.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import (
    CodexSecondOpinionConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _build_answers(*, enabled: bool) -> InterviewAnswers:
    return InterviewAnswers(
        preset=Preset.SIDE,
        targets=[Target.CLAUDE_CODE],
        codex_second_opinion=CodexSecondOpinionConfig(enabled=enabled),
    )


def test_legacy_yaml_without_key_loads_with_default(tmp_path: Path) -> None:
    """harness.yaml missing the key loads with default (enabled=False)."""
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
    assert answers.codex_second_opinion.enabled is False
    assert answers.codex_second_opinion.agents == [
        "code-reviewer",
        "consensus-arbiter",
        "plan-validator",
    ]


def test_yaml_with_block_round_trips(tmp_path: Path) -> None:
    """Render → load → re-render produces a stable codex_second_opinion block.

    enabled=True forward emit is read back as enabled=True; the field survives
    the synthesize → render → answers_from_harness_yaml cycle.
    """
    answers_in = _build_answers(enabled=True)
    bp = synthesize(ProjectProfile(), answers_in)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    yaml_path = tmp_path / "harness.yaml"
    assert yaml_path.exists()
    body = yaml_path.read_text()
    # Forward emit MUST include the block (matches feedback/second_brain pattern).
    assert "codex_second_opinion:" in body, "harness.yaml missing codex_second_opinion block"
    assert "enabled: true" in body
    # Reverse round-trip preserves enabled=True.
    restored = answers_from_harness_yaml(yaml_path)
    assert restored.codex_second_opinion.enabled is True


def test_disabled_yaml_emits_block_with_enabled_false(tmp_path: Path) -> None:
    """Forward writer emits the block even when enabled=False (matches
    existing pattern for second_brain/feedback — unconditional emit)."""
    answers_in = _build_answers(enabled=False)
    bp = synthesize(ProjectProfile(), answers_in)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    body = (tmp_path / "harness.yaml").read_text()
    assert "codex_second_opinion:" in body, (
        "harness.yaml must emit codex_second_opinion block unconditionally (ADR-005 P-W2)"
    )
    assert "enabled: false" in body
