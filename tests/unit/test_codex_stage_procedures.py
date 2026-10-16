"""Tests for Codex stage procedure embedding — RED before Phase 1-3 implementation.

Verifies that:
- _codex_stage_skills() passes stage_body in context (Phase 1)
- stage_body contains stage-specific procedure keywords (Phase 1+2)
- hm-loop SKILL.md has interview procedure and uses request_user_input (Phase 1+3)
- Claude Code + Cursor renders use dual-name pattern (regression guard)
- AskUserQuestion is absent in all Codex renders; request_user_input present (all 7 stages + loop)
- config_dump is threaded from synthesize() through to stage_body rendering
- stage_skill.md.j2 does not double-render stage_body containing Jinja2 fragments
"""

from __future__ import annotations

from typing import Any

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.synthesize import (
    _HARNESS_MAKER_PKG_ROOT,
    _codex_stage_skills,
)


def _make_default_config() -> dict[str, Any]:
    return HarnessConfig().model_dump(mode="json")


def _render_stage(stage: str, *, is_codex: bool = False) -> str:
    env = _make_env()
    cfg = _make_default_config()
    return env.get_template(f"stages/{stage}.md.j2").render(
        stage=stage,
        workflow_context="",
        project_name="",
        feature="",
        config=cfg,
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
        is_codex=is_codex,
    )


def _render_loop(*, is_codex: bool = False, worktree_enabled: bool = True) -> str:
    """Defaults to isolation ON — the worktree create/verify/fallback machinery only
    renders there (PLAN-worktree-side-defaults ADR-005), and a bare `HarnessConfig()`
    has `worktree: {}`, which reads as OFF."""
    env = _make_env()
    cfg = _make_default_config()
    cfg["worktree"] = {"enabled": worktree_enabled}
    return env.get_template("commands/hm/loop.md.j2").render(
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
        is_codex=is_codex,
        config=cfg,
    )


# ── Phase 1: stage_body in _codex_stage_skills() context ─────────────────────


def test_codex_stage_skills_context_has_stage_body() -> None:
    """_codex_stage_skills() must include stage_body in every context dict."""
    specs = _codex_stage_skills()
    for _tpl, path, ctx in specs:
        assert "stage_body" in ctx, f"Missing stage_body in context for {path}"
        assert ctx["stage_body"], f"stage_body is empty for {path}"




def test_codex_stage_skills_no_dollar_arguments() -> None:
    """No Codex stage skill body should contain '$ARGUMENTS' (Codex has no slash-args)."""
    for _tpl, path, ctx in _codex_stage_skills():
        body = ctx.get("stage_body", "")
        assert "$ARGUMENTS" not in body, (
            f"{path} stage_body contains '$ARGUMENTS' — must use natural-language parsing"
        )


# ── Phase 1: loop_body in _codex_target_files() context ──────────────────────






# ── Phase 2+3: is_codex render adaptations ───────────────────────────────────


def test_execute_codex_render_no_dollar_arguments() -> None:
    """execute stage rendered with is_codex=True must not contain '$ARGUMENTS'."""
    rendered = _render_stage("execute", is_codex=True)
    assert "$ARGUMENTS" not in rendered, (
        "Codex execute render contains '$ARGUMENTS' — must use natural-language parsing"
    )




def test_execute_codex_render_no_bang_prefix() -> None:
    """execute stage rendered with is_codex=True must not use '!uv run' shell prefix."""
    rendered = _render_stage("execute", is_codex=True)
    assert "!uv run" not in rendered, (
        "Codex execute render must not use '!' prefix — Codex uses Bash() tool calls"
    )














# ── AskUserQuestion absent in all Codex renders; request_user_input present ───

_ALL_STAGES = ["execute", "research", "spec", "review", "wrapup", "verify"]

_STAGES_WITH_INTERVIEW = ["research", "spec", "verify"]














def test_research_codex_render_no_dollar_arguments() -> None:
    """research rendered with is_codex=True must not contain $ARGUMENTS."""
    rendered = _render_stage("research", is_codex=True)
    assert "$ARGUMENTS" not in rendered, "Codex research render contains $ARGUMENTS"






# ── Config threading: config_dump flows into stage_body ───────────────────────








# ── stage_skill.md.j2 double-render safety ────────────────────────────────────


def test_stage_skill_renders_stage_body_without_double_rendering() -> None:
    """stage_skill.md.j2 must output stage_body literally, not re-interpret Jinja2 fragments."""
    env = _make_env()
    tpl = env.get_template("codex/stage_skill.md.j2")
    jinja_fragment = "Use {{ config.work_docs.dir }} for your plan files."
    # `config` is required by the included step_manifest partial — pass it as the real render
    # does. Note this also makes the assertion sharper: `config` is now genuinely defined, so
    # a double-render would resolve `{{ config.work_docs.dir }}` instead of raising.
    rendered = tpl.render(
        stage="execute",
        stage_body=jinja_fragment,
        config=HarnessConfig().model_dump(mode="json"),
        harness_maker_src_path="/fake/src/path",
    )
    assert jinja_fragment in rendered, (
        "stage_skill.md.j2 double-rendered stage_body — {{ fragments }} must appear literally"
    )


# ── Claude Code regression guards ────────────────────────────────────────────






