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


def test_side_file_count_in_range() -> None:
    assert 25 <= len(SIDE_FILES) <= 30


def test_production_file_count_in_range() -> None:
    assert 35 <= len(PRODUCTION_FILES) <= 45


def test_synthesize_side_returns_blueprint() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    assert isinstance(bp, Blueprint)
    assert bp.config.preset == Preset.SIDE
    # Phase 6: workflow commands are dynamic, so total = static base + N workflows
    assert len(bp.files) == len(SIDE_FILES) + len(a.workflow_names)
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
    assert len(bp.files) == len(PRODUCTION_FILES) + len(a.workflow_names)


def test_synthesize_auto_derives_production_from_consensus() -> None:
    p = _profile(scale="medium", lifecycle="active")
    a = interview(p, autoloop_mode=True)
    # autoloop on a medium/active profile selects 'cross-check' → Production
    bp = synthesize(p, a)
    assert bp.config.preset == Preset.PRODUCTION


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


def test_synthesize_atomic_command_count() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    atomic_paths = [str(f.path) for f in bp.files if str(f.path).startswith("commands/hm/")]
    # Side: 7 atomic + 1 workflow (dev) + 3 fixed (loop, monitor, refresh) = 11
    assert len(atomic_paths) == 11


def test_synthesize_context_carries_preset() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    for f in bp.files:
        assert f.context["preset"] == bp.config.preset.value
