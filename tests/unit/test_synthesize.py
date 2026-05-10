"""Tests for the Synthesizer (Task 3.1)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.interview import interview
from harness_maker.models import Blueprint, FileEntry, Preset, ProjectProfile
from harness_maker.synthesize import (
    PRODUCTION_FILES,
    SIDE_FILES,
    _base_files,
    _localized,
    synthesize,
)


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
    # 17 atomic+stages+fixed + 12 agents + 11 skills + harness/settings/CLAUDE/memory/etc.
    assert 40 <= len(SIDE_FILES) <= 60


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
    """Side starter set has 3 fused + 7 atomic + 6 fixed = 16 commands/hm/."""
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    cmd_paths = [str(f.path) for f in bp.files if str(f.path).startswith("commands/hm/")]
    # atomic(7) + fixed(6: loop/ai-readiness/refresh/make/configure/uninstall) + fused
    expected = 7 + 6 + len(a.fused_workflows)
    assert len(cmd_paths) == expected


def test_synthesize_includes_make_command() -> None:
    """Phase 1: /hm:make command template must be in the generated file list."""
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    paths = {str(f.path) for f in bp.files}
    assert "commands/hm/make.md" in paths


def test_synthesize_includes_configure_command() -> None:
    """Phase 6: /hm:configure command template must be in the generated file list."""
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    paths = {str(f.path) for f in bp.files}
    assert "commands/hm/configure.md" in paths


def test_synthesize_includes_uninstall_command() -> None:
    """Phase 7: /hm:uninstall command template must be in the generated file list."""
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    paths = {str(f.path) for f in bp.files}
    assert "commands/hm/uninstall.md" in paths


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


# ──────────────────────────────────────────────────────────────────────────────
# Cursor target — Phase 2.2/2.3
# ──────────────────────────────────────────────────────────────────────────────


def test_synthesize_no_cursor_target_omits_cursor_files() -> None:
    """targets=[claude-code]: regression 0 — `.cursor/` 자산 안 나옴."""
    from harness_maker.models import Target

    p = _profile()
    a = interview(p, autoloop_mode=True)
    assert a.targets == [Target.CLAUDE_CODE]  # autoloop default
    bp = synthesize(p, a)
    paths = {str(f.path) for f in bp.files}
    assert not any(p.startswith(".cursor/") for p in paths)


def test_synthesize_cursor_target_includes_cursor_files() -> None:
    """targets=[cursor]: `.cursor/rules/harness.mdc` + `.cursor/mcp.json` 추가."""
    from harness_maker.models import Target

    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CURSOR]})
    bp = synthesize(p, a)
    paths = {str(f.path) for f in bp.files}
    assert ".cursor/rules/harness.mdc" in paths
    assert ".cursor/mcp.json" in paths


def test_synthesize_both_targets_include_claude_and_cursor_files() -> None:
    """targets=[claude-code, cursor]: 모든 공유 자산 + Cursor 전용 자산."""
    from harness_maker.models import Target

    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE, Target.CURSOR]},
    )
    bp = synthesize(p, a)
    paths = {str(f.path) for f in bp.files}
    # 공유 자산 (.claude/) — single source
    assert "harness.yaml" in paths
    assert "settings.json" in paths
    # Cursor 전용
    assert ".cursor/rules/harness.mdc" in paths
    assert ".cursor/mcp.json" in paths


def test_synthesize_targets_propagates_to_harness_config() -> None:
    """`answers.targets` 가 `config.targets` 로 박혀 yaml 에 출력됨."""
    from harness_maker.models import Target

    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE, Target.CURSOR]},
    )
    bp = synthesize(p, a)
    assert bp.config.targets == [Target.CLAUDE_CODE, Target.CURSOR]


# ──────────────────────────────────────────────────────────────────────────────
# Codex target — Phase 1 stub + integration
# ──────────────────────────────────────────────────────────────────────────────


def test_synthesize_no_codex_target_omits_codex_files() -> None:
    """targets=[claude-code] (default): .codex/ and .agents/ paths never emitted."""
    from harness_maker.models import Target

    p = _profile()
    a = interview(p, autoloop_mode=True)
    assert a.targets == [Target.CLAUDE_CODE]
    bp = synthesize(p, a)
    paths = {str(f.path) for f in bp.files}
    assert not any(fp.startswith(".codex/") for fp in paths)
    assert not any(fp.startswith(".agents/") for fp in paths)
    assert "AGENTS.md" not in paths


def test_synthesize_codex_target_files_importable() -> None:
    """_codex_target_files() is importable and returns a list (stub)."""
    from harness_maker.synthesize import _codex_target_files

    result = _codex_target_files()
    assert isinstance(result, list)


def test_synthesize_codex_target_propagates_to_config() -> None:
    """targets=[codex] propagates to blueprint config.targets."""
    from harness_maker.models import Target

    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CODEX]})
    bp = synthesize(p, a)
    assert bp.config.targets == [Target.CODEX]


# ──────────────────────────────────────────────────────────────────────────────
# Locale routing — _localized() helper + _base_files() locale fan-out
# ──────────────────────────────────────────────────────────────────────────────


def test_localized_returns_en_for_english_locale() -> None:
    assert _localized("claude-md/Side", "en") == "claude-md/Side.en.md.j2"


def test_localized_returns_ko_for_korean_locale() -> None:
    assert _localized("claude-md/Side", "ko") == "claude-md/Side.ko.md.j2"


def test_localized_falls_back_to_en_for_unknown_locale() -> None:
    """Free-text locales (any tag) silently route to en — matches i18n.t() behavior."""
    assert _localized("memory/wiki", "ja") == "memory/wiki.en.md.j2"
    assert _localized("memory/wiki", "fr-CA") == "memory/wiki.en.md.j2"
    assert _localized("memory/wiki", "") == "memory/wiki.en.md.j2"


def test_base_files_default_locale_is_en() -> None:
    specs = _base_files(Preset.SIDE)
    templates = {t for t, _, _ in specs}
    assert "claude-md/Side.en.md.j2" in templates
    assert "memory/failures.en.md.j2" in templates
    assert "memory/wiki.en.md.j2" in templates


def test_base_files_routes_to_ko_when_requested() -> None:
    specs = _base_files(Preset.SIDE, "ko")
    templates = {t for t, _, _ in specs}
    assert "claude-md/Side.ko.md.j2" in templates
    assert "memory/failures.ko.md.j2" in templates
    assert "memory/wiki.ko.md.j2" in templates


def test_base_files_unknown_locale_falls_back_to_en() -> None:
    specs = _base_files(Preset.PRODUCTION, "fr")
    templates = {t for t, _, _ in specs}
    assert "claude-md/Production.en.md.j2" in templates
    assert "memory/failures.en.md.j2" in templates


def test_synthesize_with_en_locale_picks_en_templates() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(update={"locale": "en"})
    bp = synthesize(p, a)
    # locate the CLAUDE.md FileEntry — its `template` field tells us what was picked
    claude_md = next(f for f in bp.files if str(f.path) == "../CLAUDE.md")
    assert claude_md.template == "claude-md/Side.en.md.j2"


def test_synthesize_with_ko_locale_picks_ko_templates() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(update={"locale": "ko"})
    bp = synthesize(p, a)
    claude_md = next(f for f in bp.files if str(f.path) == "../CLAUDE.md")
    assert claude_md.template == "claude-md/Side.ko.md.j2"


def test_localized_template_files_exist_on_disk() -> None:
    """Each path that `_localized()` can return must point at a real template file.

    Guards against silent breakage when someone removes a template without
    updating the locale routing.
    """
    template_dir = Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates"
    for stem in ("claude-md/Side", "claude-md/Production", "memory/failures", "memory/wiki"):
        for locale in ("en", "ko"):
            path = template_dir / _localized(stem, locale)
            assert path.is_file(), f"missing template: {path}"
