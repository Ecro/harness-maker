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
