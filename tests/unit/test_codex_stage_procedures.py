"""Tests for Codex stage procedure embedding — RED before Phase 1-3 implementation.

Verifies that:
- _codex_stage_skills() passes stage_body in context (Phase 1)
- stage_body contains stage-specific procedure keywords (Phase 1+2)
- hm-loop SKILL.md has interview procedure and no AskUserQuestion (Phase 1+3)
- Claude Code renders are unchanged (regression guard)
- AskUserQuestion is absent in all Codex renders (all 7 stages + loop)
- config_dump is threaded from synthesize() through to stage_body rendering
- stage_skill.md.j2 does not double-render stage_body containing Jinja2 fragments
"""

from __future__ import annotations

import pytest

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.synthesize import (
    _HARNESS_MAKER_PKG_ROOT,
    _codex_stage_skills,
    _codex_target_files,
)


def _make_default_config() -> dict:
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


def _render_loop(*, is_codex: bool = False) -> str:
    env = _make_env()
    cfg = _make_default_config()
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


@pytest.mark.parametrize(
    ("stage", "must_contain"),
    [
        ("execute", "worktree"),
        ("research", "sources"),
        ("spec", "scenario"),
        ("plan", "phase"),
        ("review", "grade"),
        ("verify", "criterion"),
        ("wrapup", "commit"),
    ],
)
def test_codex_stage_skill_has_procedure_content(stage: str, must_contain: str) -> None:
    """stage_body in _codex_stage_skills() must contain stage-specific content."""
    specs = _codex_stage_skills()
    spec = next((s for s in specs if f"hm-{stage}" in s[1]), None)
    assert spec is not None, f"No stage skill spec found for hm-{stage}"
    body = spec[2].get("stage_body", "")
    assert must_contain in body.lower(), (
        f"hm-{stage} stage_body missing '{must_contain}' — procedure content absent"
    )


def test_codex_stage_skills_no_dollar_arguments() -> None:
    """No Codex stage skill body should contain '$ARGUMENTS' (Codex has no slash-args)."""
    for _tpl, path, ctx in _codex_stage_skills():
        body = ctx.get("stage_body", "")
        assert "$ARGUMENTS" not in body, (
            f"{path} stage_body contains '$ARGUMENTS' — must use natural-language parsing"
        )


# ── Phase 1: loop_body in _codex_target_files() context ──────────────────────


def test_codex_target_files_loop_skill_has_loop_body() -> None:
    """_codex_target_files() must include loop_body in hm-loop/SKILL.md context."""
    specs = _codex_target_files({})
    loop_spec = next(
        (s for s in specs if s[1] == ".agents/skills/hm-loop/SKILL.md"), None
    )
    assert loop_spec is not None, "hm-loop/SKILL.md not found in _codex_target_files()"
    ctx = loop_spec[2]
    assert "loop_body" in ctx, "hm-loop context missing loop_body"
    assert ctx["loop_body"], "loop_body in hm-loop context is empty"


def test_codex_loop_skill_has_interview_content() -> None:
    """hm-loop loop_body must contain adaptive interview content."""
    specs = _codex_target_files({})
    loop_spec = next(s for s in specs if s[1] == ".agents/skills/hm-loop/SKILL.md")
    loop_body = loop_spec[2].get("loop_body", "")
    assert "interview" in loop_body.lower() or "adaptive" in loop_body.lower(), (
        "hm-loop body must contain interview procedure"
    )


# ── Phase 2+3: is_codex render adaptations ───────────────────────────────────


def test_execute_codex_render_no_dollar_arguments() -> None:
    """execute stage rendered with is_codex=True must not contain '$ARGUMENTS'."""
    rendered = _render_stage("execute", is_codex=True)
    assert "$ARGUMENTS" not in rendered, (
        "Codex execute render contains '$ARGUMENTS' — must use natural-language parsing"
    )


def test_execute_codex_render_has_bash_worktree_call() -> None:
    """execute stage rendered with is_codex=True must use Bash() for worktree create."""
    rendered = _render_stage("execute", is_codex=True)
    assert "Bash(" in rendered, (
        "Codex execute render must use Bash(...) form for CLI calls, not '!' prefix"
    )
    assert "worktree" in rendered.lower(), (
        "Codex execute render must mention worktree creation"
    )


def test_execute_codex_render_no_bang_prefix() -> None:
    """execute stage rendered with is_codex=True must not use '!uv run' shell prefix."""
    rendered = _render_stage("execute", is_codex=True)
    assert "!uv run" not in rendered, (
        "Codex execute render must not use '!' prefix — Codex uses Bash() tool calls"
    )


def test_loop_codex_render_no_ask_user_question() -> None:
    """loop template rendered with is_codex=True must not contain 'AskUserQuestion'."""
    rendered = _render_loop(is_codex=True)
    assert "AskUserQuestion" not in rendered, (
        "Codex loop render contains 'AskUserQuestion' — Codex uses response-based asking"
    )


def test_loop_codex_render_has_interview_and_bash() -> None:
    """loop template rendered with is_codex=True must have interview pattern and Bash calls."""
    rendered = _render_loop(is_codex=True)
    assert (
        "ask" in rendered.lower() or "in your response" in rendered.lower()
    ), "Codex loop must have response-based asking pattern"
    assert rendered.count("Bash(") >= 3, (
        f"Codex loop must have ≥3 Bash tool calls, got {rendered.count('Bash(')}"
    )


def test_loop_codex_render_has_worktree_fallback() -> None:
    """loop template rendered with is_codex=True must document worktree failure fallback."""
    rendered = _render_loop(is_codex=True)
    assert (
        "in-place" in rendered.lower() or "worktree create fails" in rendered.lower()
        or "proceeding in-place" in rendered.lower()
    ), "Codex loop must document worktree fallback path (ADR-005)"


def test_loop_codex_render_keeps_marker_on_non_convergence() -> None:
    """Non-converged Codex loop halts must keep the Stop-hook marker active."""
    rendered = _render_loop(is_codex=True)
    assert "Keep `.hm-loop-active` on every non-converged halt" in rendered
    assert "explicitly chooses Abort/Override" in rendered


# ── AskUserQuestion absent in all Codex renders ───────────────────────────────

_ALL_STAGES = ["execute", "research", "spec", "plan", "review", "wrapup", "verify"]


@pytest.mark.parametrize("stage", _ALL_STAGES)
def test_codex_stage_render_no_ask_user_question(stage: str) -> None:
    """Every stage rendered with is_codex=True must not contain 'AskUserQuestion'."""
    rendered = _render_stage(stage, is_codex=True)
    assert "AskUserQuestion" not in rendered, (
        f"Codex {stage} render contains 'AskUserQuestion' — Codex has no tool UI"
    )


@pytest.mark.parametrize("stage", _ALL_STAGES)
def test_codex_stage_render_non_empty(stage: str) -> None:
    """Every stage rendered with is_codex=True must produce non-empty content."""
    rendered = _render_stage(stage, is_codex=True)
    assert rendered.strip(), f"Codex {stage} render is empty"


@pytest.mark.parametrize("stage", _ALL_STAGES)
def test_claude_code_stage_render_non_empty(stage: str) -> None:
    """Every stage rendered with is_codex=False must produce non-empty content."""
    rendered = _render_stage(stage, is_codex=False)
    assert rendered.strip(), f"Claude Code {stage} render is empty"


@pytest.mark.parametrize(
    ("stage", "terms"),
    [
        ("research", ["second_brain", "reference", "project"]),
        ("plan", ["second_brain", "decision", "preference"]),
        ("review", ["second_brain", "failure", "preference"]),
        ("wrapup", ["second_brain", "journal", "decision"]),
    ],
)
def test_stage_aware_second_brain_guidance(stage: str, terms: list[str]) -> None:
    rendered = _render_stage(stage, is_codex=True).lower()
    for term in terms:
        assert term in rendered
    assert "harness_maker.second_brain" in rendered
    assert "untrusted reference" in rendered


def test_research_claude_code_render_has_dollar_arguments() -> None:
    """research rendered with is_codex=False must retain $ARGUMENTS (CC slash-arg)."""
    rendered = _render_stage("research", is_codex=False)
    assert "$ARGUMENTS" in rendered, "CC research render lost $ARGUMENTS"


def test_research_codex_render_no_dollar_arguments() -> None:
    """research rendered with is_codex=True must not contain $ARGUMENTS."""
    rendered = _render_stage("research", is_codex=True)
    assert "$ARGUMENTS" not in rendered, "Codex research render contains $ARGUMENTS"


def test_research_stage_requires_user_workflow_discovery_lens() -> None:
    """research must calibrate product/user workflow discovery before pure benchmarks."""
    rendered = _render_stage("research")
    assert "Discovery lens calibration" in rendered
    assert "User-workflow / product opportunity" in rendered
    assert "Local capability x User artifact" in rendered
    assert "arXiv papers, benchmarks, and leaderboards cannot satisfy this guard" in rendered


def test_codex_research_skill_inherits_user_workflow_discovery_lens() -> None:
    """Codex hm-research skill must inherit the same discovery guard from the template."""
    specs = _codex_stage_skills()
    spec = next((s for s in specs if "hm-research" in s[1]), None)
    assert spec is not None, "No stage skill spec found for hm-research"
    body = spec[2].get("stage_body", "")
    assert "Discovery lens calibration" in body
    assert "run the **User-workflow / product opportunity**" in body
    assert "Local capability x User artifact" in body


# ── Config threading: config_dump flows into stage_body ───────────────────────


def test_codex_stage_skills_uses_passed_config_dump() -> None:
    """_codex_stage_skills() must use the passed config_dump, not HarnessConfig() defaults."""
    custom_config = _make_default_config()
    custom_config["work_docs"] = {"dir": "custom-tasks/"}
    specs = _codex_stage_skills(config_dump=custom_config)
    execute_spec = next(s for s in specs if "hm-execute" in s[1])
    body = execute_spec[2]["stage_body"]
    assert "custom-tasks/" in body, (
        "_codex_stage_skills() did not use passed config_dump — custom work_docs.dir absent"
    )


def test_codex_target_files_threads_config_dump_to_stage_skills() -> None:
    """config_dump passed to _codex_target_files() must reach the stage skill bodies."""
    custom_config = _make_default_config()
    custom_config["work_docs"] = {"dir": "my-work/"}
    specs = _codex_target_files({}, config_dump=custom_config)
    execute_skill = next(s for s in specs if s[1] == ".agents/skills/hm-execute/SKILL.md")
    body = execute_skill[2]["stage_body"]
    assert "my-work/" in body, (
        "_codex_target_files() did not thread config_dump to _codex_stage_skills()"
    )


# ── stage_skill.md.j2 double-render safety ────────────────────────────────────


def test_stage_skill_renders_stage_body_without_double_rendering() -> None:
    """stage_skill.md.j2 must output stage_body literally, not re-interpret Jinja2 fragments."""
    env = _make_env()
    tpl = env.get_template("codex/stage_skill.md.j2")
    jinja_fragment = "Use {{ config.work_docs.dir }} for your plan files."
    rendered = tpl.render(stage="execute", stage_body=jinja_fragment)
    assert jinja_fragment in rendered, (
        "stage_skill.md.j2 double-rendered stage_body — {{ fragments }} must appear literally"
    )


# ── Claude Code regression guards ────────────────────────────────────────────


def test_execute_claude_code_render_preserved() -> None:
    """execute rendered with is_codex=False (default) must retain CC-specific constructs."""
    rendered = _render_stage("execute", is_codex=False)
    assert "$ARGUMENTS" in rendered, "CC execute render lost $ARGUMENTS"
    assert "!uv run" in rendered, "CC execute render lost '!' prefix"


def test_loop_claude_code_render_preserved() -> None:
    """loop rendered with is_codex=False must retain CC-specific constructs."""
    rendered = _render_loop(is_codex=False)
    assert "$ARGUMENTS" in rendered, "CC loop render lost $ARGUMENTS"
    assert "AskUserQuestion" in rendered, "CC loop render lost AskUserQuestion"
