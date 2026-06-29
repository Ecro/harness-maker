"""Shared main-loop Codex partial (codex_exec_mainloop) inclusion in stages.

PLAN-codex-second-opinion-sandbox ADR-002/004: the invoke+adapt+skip-relay recipe
lives in ONE partial `agents/_partials/codex_exec_mainloop.md.j2`, included by the
review + plan STAGES (the main loop). It is NOT included by any reviewer agent —
the old per-agent exec section `<!-- @hm:codex-second-opinion -->` is deleted. Uses
`{%- ... -%}` whitespace control so the disabled branch is byte-zero.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import (
    CodexSecondOpinionConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, _make_env, render
from harness_maker.synthesize import synthesize

_OLD_EXEC_MARKER = "<!-- @hm:codex-second-opinion -->"
_PARTIAL = "agents/_partials/codex_exec_mainloop.md.j2"


def _render(tmp_path: Path, *, enabled: bool, preset: Preset = Preset.PRODUCTION) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=preset,
            targets=[Target.CLAUDE_CODE],
            codex_second_opinion=CodexSecondOpinionConfig(enabled=enabled),
        ),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return {
        str(f.relative_to(tmp_path)): f.read_text(encoding="utf-8") for f in tmp_path.rglob("*.md")
    }


def _stage(files: dict[str, str], name: str) -> str:
    return next(t for p, t in files.items() if p.endswith(f"stages/{name}.md"))


def test_recipe_present_in_review_and_plan_stages_when_enabled(tmp_path: Path) -> None:
    files = _render(tmp_path, enabled=True)
    for stage in ("review", "plan"):
        body = _stage(files, stage)
        assert "codex exec" in body, f"{stage} stage missing codex exec recipe"
        assert "dangerouslyDisableSandbox" in body, f"{stage} stage missing sandbox directive"
        assert "codex_adapter" in body, f"{stage} stage missing adapter step"


def test_recipe_absent_from_stages_when_disabled(tmp_path: Path) -> None:
    files = _render(tmp_path, enabled=False)
    for stage in ("review", "plan"):
        body = _stage(files, stage)
        assert "codex exec" not in body
        assert "dangerouslyDisableSandbox" not in body


def test_old_exec_section_deleted_from_all_agents(tmp_path: Path) -> None:
    files = _render(tmp_path, enabled=True)
    for path, body in files.items():
        if path.startswith("agents/"):
            assert _OLD_EXEC_MARKER not in body, f"{path} still carries the deleted exec section"
            assert "codex exec" not in body, f"{path} still carries a codex exec recipe"


def test_partial_byte_zero_when_disabled(tmp_path: Path) -> None:
    """The shared partial emits NOTHING when codex is disabled (absent-case rule)."""
    env = _make_env()
    tpl = env.get_template(_PARTIAL)
    out = tpl.render(config={"codex_second_opinion": {"enabled": False}}, codex_stage="review")
    assert out == "", repr(out[:80])


def test_partial_stage_param_interpolated(tmp_path: Path) -> None:
    env = _make_env()
    tpl = env.get_template(_PARTIAL)
    cfg = {
        "codex_second_opinion": {
            "enabled": True,
            "hermetic": True,
            "output_schema_path": ".claude/schemas/codex-finding.schema.json",
        }
    }
    review = tpl.render(config=cfg, codex_stage="review", harness_maker_src_path="/cache/hm/0.0.0")
    plan = tpl.render(config=cfg, codex_stage="plan", harness_maker_src_path="/cache/hm/0.0.0")
    assert "--stage review" in review
    assert "--stage plan" in plan
    for out in (review, plan):
        assert "dangerouslyDisableSandbox" in out
        assert "codex_adapter" in out
        assert "codex_ledger" in out


_CFG_ENABLED = {
    "codex_second_opinion": {
        "enabled": True,
        "hermetic": True,
        "output_schema_path": ".claude/schemas/codex-finding.schema.json",
    }
}


def test_partial_gates_sandbox_directive_on_is_codex() -> None:
    """M3 (REVIEW-2026-06-17): the Claude-Code-only `dangerouslyDisableSandbox`
    directive must NOT render for the Codex runtime (is_codex=True); a Codex
    runtime note replaces it. The codex stage skills embed this partial with
    is_codex=True (synthesize._codex_stage_skills), so an ungated directive would
    leak a Claude-only Bash-tool param into a codex-target harness.
    """
    env = _make_env()
    tpl = env.get_template(_PARTIAL)
    claude = tpl.render(
        config=_CFG_ENABLED,
        codex_stage="review",
        is_codex=False,
        harness_maker_src_path="/cache/hm/0.0.0",
    )
    codex = tpl.render(
        config=_CFG_ENABLED,
        codex_stage="review",
        is_codex=True,
        harness_maker_src_path="/cache/hm/0.0.0",
    )
    assert "dangerouslyDisableSandbox" in claude
    assert "dangerouslyDisableSandbox" not in codex
    assert "Codex runtime note" in codex
    for out in (claude, codex):
        assert "codex exec" in out
        assert "codex_adapter" in out


def test_partial_codex_exec_is_a_bare_command_for_allow_match() -> None:
    """M1/M2 (REVIEW-2026-06-17): the sandbox-disabled call must be a BARE
    `codex exec` command (its own fenced line beginning with `codex exec`) so the
    `Bash(codex exec:*)` allow rule prefix-matches it headless; and the untrusted
    diff must not sit in a double-quoted shell assignment (`$(...)` expansion).
    """
    import re

    env = _make_env()
    tpl = env.get_template(_PARTIAL)
    out = tpl.render(
        config=_CFG_ENABLED,
        codex_stage="review",
        is_codex=False,
        harness_maker_src_path="/cache/hm/0.0.0",
    )
    blocks = re.findall(r"```bash\n(.*?)\n```", out, re.DOTALL)
    assert any(b.lstrip().startswith("codex exec") for b in blocks), (
        f"no bare `codex exec` command block; blocks={[b[:40] for b in blocks]!r}"
    )
    assert 'content="' not in out, "untrusted diff must not go in a double-quoted assignment"
