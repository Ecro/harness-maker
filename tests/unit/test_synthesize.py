"""Tests for the Synthesizer (Task 3.1)."""

from __future__ import annotations

from harness_maker.interview import interview
from harness_maker.models import Blueprint, FileEntry, Preset, ProjectProfile
from harness_maker.synthesize import PRODUCTION_FILES, SIDE_FILES, synthesize


def _profile(scale: str = "small", lifecycle: str = "experiment") -> ProjectProfile:
    return ProjectProfile(
        stack=["python"],
        scale=scale,
        lifecycle=lifecycle,
    )


def test_side_and_production_install_full_inventory() -> None:
    """Both presets install the same skill+agent inventory; counts match."""
    assert len(SIDE_FILES) == len(PRODUCTION_FILES)


def test_side_file_count_in_range() -> None:
    # 17 atomic+stages+fixed + 9 agents + 10 skills + harness/settings/CLAUDE/memory/hooks/dashboard
    assert 40 <= len(SIDE_FILES) <= 50


def test_synthesize_side_returns_blueprint() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    assert isinstance(bp, Blueprint)
    assert bp.config.preset == Preset.SIDE
    # Total = static base + N fused workflow command files
    assert len(bp.files) == len(SIDE_FILES) + len(a.fused_workflows)
    for f in bp.files:
        assert isinstance(f, FileEntry)
        assert f.template
        assert f.path
        assert "preset" in f.context


def test_synthesize_production_via_explicit_preset() -> None:
    p = _profile(scale="medium", lifecycle="active")
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a, preset=Preset.PRODUCTION)
    assert bp.config.preset == Preset.PRODUCTION
    assert len(bp.files) == len(PRODUCTION_FILES) + len(a.fused_workflows)


def test_synthesize_uses_answers_preset_when_unset() -> None:
    p = _profile(scale="medium", lifecycle="active")
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    assert bp.config.preset == a.preset == Preset.PRODUCTION


def test_synthesize_deterministic_across_runs() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp1 = synthesize(p, a)
    bp2 = synthesize(p, a)
    assert [str(f.path) for f in bp1.files] == [str(f.path) for f in bp2.files]
    assert [f.template for f in bp1.files] == [f.template for f in bp2.files]


def test_synthesize_includes_harness_yaml_and_settings_json() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    paths = {str(f.path) for f in bp.files}
    assert "harness.yaml" in paths
    assert "settings.json" in paths


def test_synthesize_fused_workflow_command_count() -> None:
    """Side starter set has 3 fused workflows + 7 atomic + 3 fixed = 13 commands/hm/."""
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    cmd_paths = [str(f.path) for f in bp.files if str(f.path).startswith("commands/hm/")]
    expected = 7 + 3 + len(a.fused_workflows)  # atomic + (loop/monitor/refresh) + fused
    assert len(cmd_paths) == expected


def test_synthesize_context_carries_preset() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    for f in bp.files:
        assert f.context["preset"] == bp.config.preset.value


def test_synthesize_emits_skills_context() -> None:
    """Per-file context exposes skills installed/enabled for templates."""
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    for f in bp.files:
        assert "skills" in f.context
        assert "installed" in f.context["skills"]
        assert "enabled" in f.context["skills"]
