"""Phase 1 — AutonomyConfig schema + round-trip (PLAN-human-bottleneck-auto-advance).

ADR-002: autonomy.level default ``gated``; absent-case (old yaml without key) -> gated.
ADR-006: default pipeline = 7 atomic stages incl. verify.
ADR-003: never-auto baseline is code-fixed, NOT a config field; only ``extra_deny``
is additive. These tests are the P1 exit criterion: absent / partial / invalid-enum /
default-preservation, all through the real ``answers_from_harness_yaml`` mapper.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import (
    AtomicStage,
    AutonomyConfig,
    HarnessConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

DEFAULT_PIPELINE = [
    AtomicStage.RESEARCH,
    AtomicStage.SPEC,
    AtomicStage.PLAN,
    AtomicStage.EXECUTE,
    AtomicStage.REVIEW,
    AtomicStage.VERIFY,
    AtomicStage.WRAPUP,
]


def test_default_pipeline_runs_verify_before_wrapup() -> None:
    # P1-4 invariant: the canonical default pipeline MUST place verify (the safety check)
    # strictly before wrapup (the commit/land). The AtomicStage ENUM declares WRAPUP before
    # VERIFY, so any pipeline built from list(AtomicStage) would be wrong — the config
    # default must not be.
    pipe = AutonomyConfig().pipeline
    assert pipe.index(AtomicStage.VERIFY) < pipe.index(AtomicStage.WRAPUP)


def test_cli_autopilot_on_uses_canonical_pipeline(tmp_path: Path) -> None:
    # P1-4: `autopilot on` with no --pipeline must write the CANONICAL order (verify before
    # wrapup), NOT list(AtomicStage). Guards the CLI bare-default regression directly.
    from typer.testing import CliRunner

    from harness_maker import autopilot
    from harness_maker.cli import app

    res = CliRunner().invoke(
        app, ["autopilot", "on", "--level", "auto_safe", "--root", str(tmp_path)]
    )
    assert res.exit_code == 0, res.output
    marker = autopilot.active_marker(tmp_path)
    assert marker is not None
    assert marker.pipeline == AutonomyConfig().pipeline
    assert marker.pipeline.index(AtomicStage.VERIFY) < marker.pipeline.index(AtomicStage.WRAPUP)


# --- model defaults / validation -------------------------------------------------


def test_autonomy_default_is_auto_safe() -> None:
    """PLAN-harness-diet ADR-010 promoted the CLASS default; ADR-013 pins the fallbacks.

    The conservative sites that must NOT follow this value are asserted in
    tests/unit/test_autonomy_defaults.py.
    """
    assert AutonomyConfig().level == "auto_safe"


def test_autonomy_default_pipeline_is_seven_stage_incl_verify() -> None:
    cfg = AutonomyConfig()
    assert cfg.pipeline == DEFAULT_PIPELINE
    assert AtomicStage.VERIFY in cfg.pipeline


def test_autonomy_has_caps_and_extra_deny_defaults() -> None:
    # Pin exact ADR-007 defaults (not just > 0) so a regression to unreasonable
    # caps is caught — review finding (Reviewer B P2).
    cfg = AutonomyConfig()
    assert cfg.step_cap == 20
    assert cfg.time_cap_min == 300
    assert cfg.extra_deny == []


def test_harness_config_absent_autonomy_delivers_the_promoted_default() -> None:
    """A bare HarnessConfig is a DELIVERY site (synthesis), not a user-config load.

    Nothing validates a user's harness.yaml into this model, so inheriting the promoted
    default here cannot escalate an existing project.
    """
    cfg = HarnessConfig(preset=Preset.PRODUCTION)
    assert cfg.autonomy.level == "auto_safe"
    assert cfg.autonomy.pipeline == DEFAULT_PIPELINE


def test_autonomy_invalid_level_rejected() -> None:
    with pytest.raises(ValidationError):
        AutonomyConfig(level="yolo")  # type: ignore[arg-type]


def test_autonomy_partial_config_fills_defaults() -> None:
    cfg = AutonomyConfig(level="auto_safe")
    assert cfg.level == "auto_safe"
    assert cfg.pipeline == DEFAULT_PIPELINE
    assert cfg.step_cap > 0


def test_autonomy_never_auto_baseline_is_not_a_config_field() -> None:
    # ADR-003: the destructive deny baseline is code-fixed, never user-overridable.
    assert "never_auto" not in AutonomyConfig.model_fields
    assert "extra_deny" in AutonomyConfig.model_fields


# --- reverse-mapper (yaml load) --------------------------------------------------


def _write_yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "harness.yaml"
    p.write_text("---\ngenerated_by: harness-maker\n---\n" + body)
    return p


def test_reverse_mapper_absent_autonomy_is_gated(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "preset: Production\nlocale: en\ntargets: [claude-code]\n")
    answers = answers_from_harness_yaml(p)
    assert answers is not None
    assert answers.autonomy.level == "gated"
    assert answers.autonomy.pipeline == DEFAULT_PIPELINE


def test_reverse_mapper_roundtrips_autonomy(tmp_path: Path) -> None:
    body = (
        "preset: Production\nlocale: en\ntargets: [claude-code]\n"
        "autonomy:\n"
        "  level: auto_safe\n"
        "  pipeline: [research, plan, execute, review, wrapup]\n"
        "  step_cap: 12\n"
        "  time_cap_min: 30\n"
        "  extra_deny: ['Bash(terraform destroy:*)']\n"
    )
    p = _write_yaml(tmp_path, body)
    answers = answers_from_harness_yaml(p)
    assert answers is not None
    assert answers.autonomy.level == "auto_safe"
    assert answers.autonomy.pipeline == [
        AtomicStage.RESEARCH,
        AtomicStage.PLAN,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ]
    assert answers.autonomy.step_cap == 12
    assert answers.autonomy.time_cap_min == 30
    assert answers.autonomy.extra_deny == ["Bash(terraform destroy:*)"]


def test_reverse_mapper_invalid_level_falls_back_gated(tmp_path: Path) -> None:
    # Tolerant pattern (like second_brain/feedback): malformed block -> silent default.
    body = "preset: Production\nlocale: en\ntargets: [claude-code]\nautonomy:\n  level: yolo\n"
    p = _write_yaml(tmp_path, body)
    answers = answers_from_harness_yaml(p)
    assert answers is not None
    # Bind the FULL fallback state, not just the headline field — the fallback is a
    # whole default AutonomyConfig, not a partial recovery (Reviewer B P1).
    assert answers.autonomy.level == "gated"
    assert answers.autonomy.pipeline == DEFAULT_PIPELINE
    assert answers.autonomy.step_cap == 20
    assert answers.autonomy.extra_deny == []


def test_reverse_mapper_zero_step_cap_falls_back_default(tmp_path: Path) -> None:
    # gt=0 is enforced even under strict=False, so a hand-edited step_cap: 0 must
    # trip ValidationError → tolerant gated fallback (Reviewer B P1).
    body = (
        "preset: Production\nlocale: en\ntargets: [claude-code]\n"
        "autonomy:\n  level: auto_safe\n  step_cap: 0\n"
    )
    p = _write_yaml(tmp_path, body)
    answers = answers_from_harness_yaml(p)
    assert answers is not None
    assert answers.autonomy.level == "gated"  # whole block fell back, not partial
    assert answers.autonomy.step_cap == 20


def test_synthesize_render_reload_roundtrip(tmp_path: Path) -> None:
    answers_in = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE],
        autonomy=AutonomyConfig(level="auto_safe", step_cap=15),
    )
    bp = synthesize(ProjectProfile(), answers_in)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    yaml_path = tmp_path / "harness.yaml"
    assert yaml_path.exists()
    body = yaml_path.read_text()
    assert "autonomy:" in body, "harness.yaml must emit the autonomy block"
    # tojson quotes the scalar (valid YAML) → assert the value, not exact spacing.
    assert "auto_safe" in body
    restored = answers_from_harness_yaml(yaml_path)
    assert restored is not None
    # Verify ALL 6 fields survive synth→render→reload, not just 2 (Reviewer B P1).
    assert restored.autonomy.level == "auto_safe"
    assert restored.autonomy.step_cap == 15
    assert restored.autonomy.time_cap_min == 300
    assert restored.autonomy.pipeline == DEFAULT_PIPELINE
    assert restored.autonomy.extra_deny == []
