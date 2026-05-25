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

# PLAN-codex-mandatory-second-opinion: plan-validator's Codex call becomes
# mandatory (MAY→MUST) with a top-level reconciliation contract. The array
# reviewers (code-reviewer, consensus-arbiter) keep the opt-in MAY text until
# the follow-up PLAN (ADR-004 — their output is a top-level JSON array that
# the two-pass/verifier/consensus pipeline would strip an envelope from).
_MANDATORY_TITLE = "## Required: Codex second opinion"
_OPTIONAL_TITLE = "## Optional: Codex second opinion"
_OPT_IN_PHRASE = "opt-in per call"
_ARRAY_REVIEWERS = ("code-reviewer", "consensus-arbiter")


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


def test_plan_validator_mandatory_when_enabled(tmp_path: Path) -> None:
    """plan-validator: MAY→MUST + top-level reconciliation contract + loud-skip."""
    rendered = _render_agent_files(tmp_path, enabled=True)
    body = rendered["plan-validator"]
    # forced call (no longer opt-in)
    assert _MANDATORY_TITLE in body, "plan-validator missing the Required section title"
    assert "invoke Codex" in body, "forced-call phrasing missing"
    assert "MUST" in body, "mandatory 'MUST' phrasing missing"
    assert _OPTIONAL_TITLE not in body, "stale Optional title still present"
    assert "MAY invoke" not in body, "opt-in 'MAY invoke' phrasing not flipped"
    assert _OPT_IN_PHRASE not in body, "'opt-in per call' phrasing not removed"
    # top-level reconciliation contract + anti-boilerplate floor
    assert "codex_reconciliation" in body, "reconciliation contract missing"
    assert "codex_status" in body, "codex_status field missing"
    assert "codex_finding_ref" in body, "anti-boilerplate finding-reference floor missing"
    # loud-skip path documented
    assert "codex_skip_reason" in body, "loud-skip reason field missing"


def test_array_reviewers_unchanged_when_enabled(tmp_path: Path) -> None:
    """code-reviewer + consensus-arbiter keep opt-in MAY (deferred to follow-up PLAN)."""
    rendered = _render_agent_files(tmp_path, enabled=True)
    for agent in _ARRAY_REVIEWERS:
        body = rendered[agent]
        assert _OPTIONAL_TITLE in body, f"{agent} lost its opt-in Optional section"
        assert _OPT_IN_PHRASE in body, f"{agent} opt-in phrasing changed unexpectedly"
        # the mandatory contract must NOT leak into the array reviewers
        assert "codex_reconciliation" not in body, f"reconciliation leaked into {agent}"
        assert "codex_status" not in body, f"codex_status leaked into {agent}"
        assert _MANDATORY_TITLE not in body, f"Required title leaked into {agent}"
