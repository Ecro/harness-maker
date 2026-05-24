"""Phase 2 — second_opinion_codex partial inclusion in 3 reviewer agent bodies.

PLAN-codex-second-llm-integration ADR-007: partial conditionally rendered only
when codex_second_opinion.enabled AND agent name in the allow-list. Uses
`{%- ... -%}` whitespace control so the disabled branch is byte-zero (ADR-007
P-W1 — Jinja env has trim_blocks=False, lstrip_blocks=False).

Marker: `<!-- @hm:codex-second-opinion -->` — distinct from existing markers
to allow precise grep-based assertions.
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
_SECTION_MARKER = "<!-- @hm:codex-second-opinion -->"


def _render_agent_files(tmp_path: Path, *, enabled: bool) -> dict[str, str]:
    """Run real synthesize → render path so communication_variant injection fires."""
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


def test_second_opinion_section_present_when_enabled(tmp_path: Path) -> None:
    rendered = _render_agent_files(tmp_path, enabled=True)
    for agent in _ALLOW_LISTED:
        assert agent in rendered, f"missing agent {agent} in blueprint"
        assert _SECTION_MARKER in rendered[agent], (
            f"{_SECTION_MARKER!r} not in {agent} when codex_second_opinion enabled"
        )


def test_second_opinion_section_absent_when_disabled(tmp_path: Path) -> None:
    rendered = _render_agent_files(tmp_path, enabled=False)
    for agent, body in rendered.items():
        assert _SECTION_MARKER not in body, (
            f"{_SECTION_MARKER!r} leaked into {agent} when codex_second_opinion disabled"
        )


def test_second_opinion_section_absent_in_non_allowlisted_agents(tmp_path: Path) -> None:
    rendered = _render_agent_files(tmp_path, enabled=True)
    for agent in _NOT_ALLOW_LISTED:
        if agent not in rendered:
            continue
        assert _SECTION_MARKER not in rendered[agent], (
            f"{_SECTION_MARKER!r} leaked into NON-allow-listed agent {agent}"
        )
