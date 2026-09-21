"""Tests for the Synthesizer (Task 3.1)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import Blueprint, FileEntry, Preset, ProjectProfile
from harness_maker.render import _make_env
from harness_maker.synthesize import (
    _ALL_AGENTS,
    PRODUCTION_FILES,
    SIDE_FILES,
    _base_files,
    _codex_agent_files,
    _localized,
    synthesize,
)


def _profile(scale: str = "small", lifecycle: str = "dormant") -> ProjectProfile:
    return ProjectProfile(
        stack=["python"],
        scale=scale,
        lifecycle=lifecycle,
    )


def test_side_and_production_install_full_inventory() -> None:
    """Both presets install the same skill+agent inventory; counts match."""
    assert len(SIDE_FILES) == len(PRODUCTION_FILES)


def test_side_file_count_in_range() -> None:
    # 17 atomic+stages+fixed + _ALL_AGENTS + 11 skills + harness/settings/CLAUDE/memory etc.
    # 60 → 61 (2026-09-19, SPEC-mission-context-loop): the `project-knowledge` skill.
    # 61 → 62 → 61 (2026-09-20, SPEC-plan-stage-absorption): `spec-validator` replaced
    # `plan-validator` one-for-one. The ceiling went to 62 for the length of Phase 2, when both
    # were installed, and came back here in Phase 4 — ADR-007 found that `plan.md` stops
    # rendering the moment `AtomicStage.PLAN` goes, so nothing dispatched the old agent and the
    # transitional pair was unnecessary. A ratchet left loose stops ratcheting.
    assert 40 <= len(SIDE_FILES) <= 61


def test_synthesize_side_returns_blueprint() -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    assert isinstance(bp, Blueprint)
    assert bp.config.preset == Preset.SIDE
    # Total = static base + N fused workflow command files
    assert len(bp.files) == len(SIDE_FILES)
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
    assert len(bp.files) == len(PRODUCTION_FILES)


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
    """Side starter set has 3 fused + 7 atomic + 8 fixed = 18 commands/hm/."""
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    cmd_paths = [str(f.path) for f in bp.files if str(f.path).startswith("commands/hm/")]
    # atomic(7) + fixed(8: loop/loop-p5-batch/health/metrics/make/configure/uninstall/help) + fused.
    # /hm:health absorbed ai-readiness/refresh/personalization-audit (ADR-006).
    # /hm:help added in 0.19.4 (PLAN-help-command).
    # /hm:loop-p5-batch extracted from /hm:loop body (PLAN-latency-worktree-step-preview ADR-006).
    # /hm:metrics always rendered in 0.35.0 (ADR-002 amended — stub when disabled).
    # 7 → 6 atomic (2026-09-20, SPEC-plan-stage-absorption IRR-001): `/hm:plan` was removed.
    # `AtomicStage` is the single source for which stages render (ADR-007), so the count
    # follows the enum and there is no second place to forget.
    expected = 6 + 8
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


def test_synthesize_propagates_second_brain_config() -> None:
    from harness_maker.models import SecondBrainConfig, SecondBrainFolder

    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(
        update={
            "second_brain": SecondBrainConfig(
                enabled=True,
                project_id="harness-maker",
                vault_path="../vault",
                folders=[SecondBrainFolder(path="Projects/harness-maker", read=True, write=True)],
            )
        }
    )
    bp = synthesize(p, a)
    assert bp.config.second_brain.enabled is True
    assert bp.config.second_brain.project_id == "harness-maker"
    assert bp.config.second_brain.vault_path == "../vault"
    assert bp.config.second_brain.folders[0].write is True


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


def test_synthesize_ko_locale_propagates_into_atomic_command_body(tmp_path: Path) -> None:
    """Regression: locale must flow into stage-body pre-render.

    Bug (pre-fix): ``_atomic_command_files`` and ``fuse()`` used a fresh
    ``HarnessConfig()`` (locale defaults to ``en``) to pre-render stage
    bodies. The outer ``commands/hm/<stage>.md`` template received the real
    ``config.locale='ko'`` but the body was already a plain-text string with
    ``en`` baked in — so every ``/hm:<stage>`` instructed Claude to interview
    in English even when ``harness.yaml`` said ``locale: ko``.
    """
    from harness_maker.render import render

    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(update={"locale": "ko"})
    bp = synthesize(p, a)
    render(bp, tmp_path)

    # `plan.md` used to carry the second half of this check via its "conduct in `ko`" line.
    # SPEC-plan-stage-absorption removed the stage and that phrase existed nowhere else, so the
    # coverage moves to the other two locale-bearing stage bodies rather than shrinking to one.
    spec_text = (tmp_path / "commands/hm/spec.md").read_text()
    research_text = (tmp_path / "commands/hm/research.md").read_text()

    assert "Live UI** in `ko`" in spec_text, "spec.md still bakes en into stage body"
    assert "`ko`" in research_text, "research.md still bakes en into stage body"

    # No bare `en` directive should leak through for ko-locale renders. We
    # whitelist the legend text that lists the mapping (`en→English, ...`).
    for name, text in (("spec.md", spec_text), ("research.md", research_text)):
        en_directives = [
            line for line in text.splitlines() if "`en`" in line and "en→English" not in line
        ]
        assert not en_directives, f"unexpected en directives in {name}: {en_directives}"


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


# ── ADR-001: Codex agent TOMLs render without per-agent `model =` line ────────


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_codex_agent_toml_omits_model_field(name: str) -> None:
    """Rendered .codex/agents/<name>.toml MUST NOT contain a `model =` line.

    ChatGPT-tier Codex CLI rejects every hardcoded model string previously
    shipped (o4, o4-mini, gpt-5-codex, gpt-5.5-codex) with HTTP 400. Omitting
    the per-agent model field lets the user's ~/.codex/config.toml profile
    default win automatically. Source: ADR-001 in
    work-docs/PLAN-codex-plan-validator-model-unavailable.md.

    The template `templates/codex/agent.toml.j2` still gates rendering on
    truthy `model_codex` to preserve forward-compat when the deferred
    `codex_agent_models` knob lands; this test guards the default behavior.

    Context is built from `HarnessConfig().model_dump(mode='json')` so the
    fixture stays in lockstep with production — a hand-rolled partial dict
    would silently swallow KeyError if the template grew a new key.
    """
    from harness_maker.models import HarnessConfig

    config = HarnessConfig().model_dump(mode="json")
    specs = _codex_agent_files()
    agent_ctx = next(
        (ctx for _, out, ctx in specs if out == f".codex/agents/{name}.toml"),
        None,
    )
    assert agent_ctx is not None, f"_codex_agent_files() returned no entry for {name!r}"
    env = _make_env()
    tpl = env.get_template("codex/agent.toml.j2")
    rendered = tpl.render(**agent_ctx, config=config)
    assert not re.search(r"^model\s*=", rendered, flags=re.MULTILINE), (
        f"Rendered .codex/agents/{name}.toml still contains a `model =` line "
        f"(ADR-001 violation). Full TOML:\n{rendered}"
    )


def test_atomic_command_fallback_pins_block_strictness() -> None:
    """The no-config fallback in _atomic_command_files renders at `block` INDEPENDENT of the
    HarnessConfig class default (ADR-002 of PLAN-spec-optional-task-driven, re-keyed by
    SPEC-dev-mode-removal).

    The pin is load-bearing by construction now: the class default preset is Side, which derives
    `warn`, so a bare `HarnessConfig()` fallback would render the relaxed stop language. The
    marker is block-ONLY — the SPEC-need step itself renders at both strictness values, so
    `spec_need` alone could no longer tell the arms apart.
    """
    from harness_maker.models import HarnessConfig
    from harness_maker.strictness import resolve_strictness
    from harness_maker.synthesize import _atomic_command_files

    assert resolve_strictness(HarnessConfig()) == "warn"  # sanity: the default would NOT pin

    files = _atomic_command_files()  # no config_dump → fallback path
    body = next(ctx["stage_body"] for (_tpl, dest, ctx) in files if dest.endswith("execute.md"))
    assert "explicit FAIL signal to `/hm:verify` Check 6" in body


def test_hooks_json_not_a_blueprint_filespec() -> None:
    """Phase 4 / ADR-005 (PLAN-permission-deny-and-hooks-wiring): the retired
    `.claude/hooks/hooks.json` is no longer rendered as a blueprint FileSpec.
    Claude Code never read it; hooks now live in settings.json."""
    for specs in (SIDE_FILES, PRODUCTION_FILES):
        out_paths = {out_path for _tpl, out_path, _ctx in specs}
        assert "hooks/hooks.json" not in out_paths

    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    rendered_paths = {str(fe.path) for fe in bp.files}
    assert "hooks/hooks.json" not in rendered_paths
