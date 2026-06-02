"""Phase 2 — Bash(codex exec:*) permission injection into 3 reviewer agents.

PLAN-codex-second-llm-integration ADR-007: Jinja-conditional permission line
is included into the agent template's permissions.allow block (NOT via
_merge_permissions which is settings.json-only — validator P0#1 catch).

Contract:
- enabled=True → 3 allow-listed agents' rendered .md files contain `Bash(codex exec:*)`.
- enabled=False → 0 agents contain it.
- enabled=True + non-allow-listed agent (executor, autoloop-coder, security-auditor)
  → still 0 (writers + non-default reviewers never get the permission).
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
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_ALLOW_LISTED = ("code-reviewer", "consensus-arbiter", "plan-validator")
_NOT_ALLOW_LISTED = ("executor", "autoloop-coder", "security-auditor")
_PERMISSION_MARKER = "Bash(codex exec:*)"


def _render_agent_files(tmp_path: Path, *, enabled: bool) -> dict[str, str]:
    """Run real synthesize → render path, return {agent_name: rendered_text}.

    Uses the full render() flow (not raw template.render) so the
    communication_variant injection (render._extract_source_communication_variant)
    fires — matches production render pipeline (ADR-002 PLAN-antisycophancy-2026-05).
    """
    profile = ProjectProfile()
    answers = InterviewAnswers(
        preset=Preset.SIDE,
        targets=[Target.CLAUDE_CODE],
        codex_second_opinion=CodexSecondOpinionConfig(enabled=enabled),
    )
    blueprint = synthesize(profile, answers)
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    out: dict[str, str] = {}
    agents_dir = tmp_path / "agents"
    if not agents_dir.is_dir():
        return out
    for md_path in agents_dir.glob("*.md"):
        out[md_path.stem] = md_path.read_text(encoding="utf-8")
    return out


def test_codex_permission_present_when_enabled(tmp_path: Path) -> None:
    rendered = _render_agent_files(tmp_path, enabled=True)
    for agent in _ALLOW_LISTED:
        assert agent in rendered, f"missing agent {agent} in blueprint"
        assert _PERMISSION_MARKER in rendered[agent], (
            f"{_PERMISSION_MARKER!r} not in {agent} when codex_second_opinion enabled"
        )


def test_codex_permission_absent_when_disabled(tmp_path: Path) -> None:
    rendered = _render_agent_files(tmp_path, enabled=False)
    for agent, body in rendered.items():
        assert _PERMISSION_MARKER not in body, (
            f"{_PERMISSION_MARKER!r} leaked into {agent} when codex_second_opinion disabled"
        )


def test_codex_permission_absent_in_non_allowlisted_agents(tmp_path: Path) -> None:
    rendered = _render_agent_files(tmp_path, enabled=True)
    for agent in _NOT_ALLOW_LISTED:
        if agent not in rendered:
            continue  # agent not in this blueprint — vacuously OK
        assert _PERMISSION_MARKER not in rendered[agent], (
            f"{_PERMISSION_MARKER!r} leaked into NON-allow-listed agent {agent}"
        )


# --- Issue 1 fix (PLAN-spoton-codex-rm-stash-rootcause ADR-001) -------------
# The `tools:` frontmatter field is Claude Code's hard gate on tool
# availability; `permissions.allow: Bash(codex exec:*)` is inert unless the
# agent also lists `Bash` in `tools:`. The 3 codex agents must declare it.
_INTERPRETER_DENY_QUARTET = (
    "Bash(python:*)",
    "Bash(node:*)",
    "Bash(sh:*)",
    "Bash(bash:*)",
)


def _tools_line(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("tools:"):
            return line
    return ""


def test_codex_agents_declare_bash_tool_unconditionally(tmp_path: Path) -> None:
    """tools: must list Bash for the 3 codex agents so `codex exec` can run.

    Unconditional (ADR-001): present whether or not codex is enabled —
    `permissions` (not `tools`) scopes which Bash commands are allowed.
    """
    for enabled in (True, False):
        rendered = _render_agent_files(tmp_path, enabled=enabled)
        for agent in _ALLOW_LISTED:
            assert agent in rendered, f"missing agent {agent} in blueprint"
            line = _tools_line(rendered[agent])
            tools = [t.strip() for t in line.removeprefix("tools:").split(",")]
            assert "Bash" in tools, (
                f"{agent} tools: line lacks Bash (enabled={enabled}) — "
                f"Bash(codex exec:*) permission is inert without it. Got: {line!r}"
            )


def test_codex_agents_keep_full_interpreter_deny_quartet(tmp_path: Path) -> None:
    """Granting the Bash tool makes deny the sole barrier — it must stay complete.

    REVIEW-M7 / validator W1: rm+curl alone is bypassable via Bash(sh -c ...),
    so the python/node/sh/bash quartet must remain denied on every codex agent.
    """
    rendered = _render_agent_files(tmp_path, enabled=True)
    for agent in _ALLOW_LISTED:
        assert agent in rendered, f"missing agent {agent} in blueprint"
        body = rendered[agent]
        missing = [d for d in _INTERPRETER_DENY_QUARTET if d not in body]
        assert not missing, f"{agent} deny block missing interpreter guards: {missing}"
