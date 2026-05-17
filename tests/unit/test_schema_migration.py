"""Phase 11 — B1+B3+B6 schema + Side defaults + schema_version migration."""

from __future__ import annotations

from pathlib import Path

from harness_maker.interview import interview, _preset_extras
from harness_maker.models import HarnessConfig, InterviewAnswers, Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render_preset(tmp_path: Path, preset: Preset) -> Path:
    profile = (
        ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
        if preset == Preset.SIDE
        else ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    )
    a = interview(profile, autoloop_mode=True)
    bp = synthesize(profile, a, preset=preset)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def test_side_defaults_new_fields_schema_v2(tmp_path: Path) -> None:
    """New Side harness (schema v2) should get reduced caps."""
    out = _render_preset(tmp_path, Preset.SIDE)
    import yaml

    docs = list(yaml.safe_load_all((out / "harness.yaml").read_text(encoding="utf-8")))
    hy = [d for d in docs if d and isinstance(d, dict) and "preset" in d][0]
    assert hy["schema_version"] == 2
    assert hy["interview"]["deep_gate"]["max_rounds"] == 1
    assert hy["interview"]["deep_gate"]["streak_target"] == 1
    assert hy["interview"]["main_loop"]["max_rounds"] == 5


def test_side_defaults_old_fields_schema_v1_or_missing() -> None:
    """Old Side harness (schema v1) should keep old defaults (C3 backward compat)."""
    extras = _preset_extras(Preset.SIDE, schema_version=1)
    assert extras["interview"]["deep_gate"]["max_rounds"] == 3
    assert extras["interview"]["deep_gate"]["streak_target"] == 2
    assert extras["interview"]["main_loop"]["max_rounds"] is None
    assert extras["max_review_rounds"] == 3


def test_prod_defaults_unchanged_across_schema_versions() -> None:
    """Production defaults should be identical regardless of schema_version."""
    v1 = _preset_extras(Preset.PRODUCTION, schema_version=1)
    v2 = _preset_extras(Preset.PRODUCTION, schema_version=2)
    assert v1["interview"] == v2["interview"]
    assert v1["interview"]["deep_gate"]["max_rounds"] == 3


def test_interview_py_injects_side_v2() -> None:
    """interview() for Side should inject schema_version=2 and new caps."""
    extras = _preset_extras(Preset.SIDE, schema_version=2)
    assert extras["schema_version"] == 2
    assert extras["interview"]["deep_gate"]["max_rounds"] == 1
    assert extras["max_review_rounds"] == 2


def test_interview_py_preserves_side_v1_old_defaults() -> None:
    """Side v1 must preserve old-style defaults (C3)."""
    extras = _preset_extras(Preset.SIDE, schema_version=1)
    assert extras["schema_version"] == 1
    assert extras["interview"]["deep_gate"]["max_rounds"] == 3
    assert extras["interview"]["deep_gate"]["streak_target"] == 2


def test_schema_version_field_present_in_models() -> None:
    """Both HarnessConfig and InterviewAnswers should have schema_version."""
    hc = HarnessConfig()
    assert hasattr(hc, "schema_version")
    assert hc.schema_version == 1

    ia = InterviewAnswers()
    assert hasattr(ia, "schema_version")
    assert ia.schema_version == 2


def test_stage_template_reads_config_not_hardcoded(tmp_path: Path) -> None:
    """Stage templates should use config values, not hardcoded numbers."""
    out = _render_preset(tmp_path, Preset.SIDE)
    research = (out / "stages" / "research.md").read_text(encoding="utf-8")
    assert "streak: {N}/1" in research
    assert "**1 consecutive rounds**" in research
    assert "Max **1 rounds**" in research

    out_prod = _render_preset(tmp_path / "prod", Preset.PRODUCTION)
    research_prod = (out_prod / "stages" / "research.md").read_text(encoding="utf-8")
    assert "streak: {N}/2" in research_prod
    assert "**2 consecutive rounds**" in research_prod
    assert "Max **3 rounds**" in research_prod


def test_plan_template_reads_main_loop_config(tmp_path: Path) -> None:
    """Plan template should use interview.main_loop.max_rounds from config."""
    out = _render_preset(tmp_path, Preset.SIDE)
    plan = (out / "stages" / "plan.md").read_text(encoding="utf-8")
    assert "up to 5 rounds" in plan

    out_prod = _render_preset(tmp_path / "prod", Preset.PRODUCTION)
    plan_prod = (out_prod / "stages" / "plan.md").read_text(encoding="utf-8")
    assert "unlimited rounds" in plan_prod
