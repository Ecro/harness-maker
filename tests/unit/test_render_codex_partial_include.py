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


def _render_agent_files(
    tmp_path: Path, *, enabled: bool, preset: Preset = Preset.SIDE
) -> dict[str, str]:
    """Run real synthesize → render path so communication_variant injection fires."""
    profile = ProjectProfile()
    answers = InterviewAnswers(
        preset=preset,
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


def test_plan_validator_production_always_mandatory(tmp_path: Path) -> None:
    """Production plan-validator: always-MUST + reconciliation envelope (ADR-002 matrix)."""
    rendered = _render_agent_files(tmp_path, enabled=True, preset=Preset.PRODUCTION)
    body = rendered["plan-validator"]
    assert _MANDATORY_TITLE in body, "plan-validator missing the Required section title"
    assert "invoke Codex" in body, "forced-call phrasing missing"
    assert "MUST" in body, "mandatory 'MUST' phrasing missing"
    assert _OPTIONAL_TITLE not in body, "stale Optional title still present"
    assert "MAY invoke" not in body, "opt-in 'MAY invoke' phrasing not flipped"
    assert _OPT_IN_PHRASE not in body, "'opt-in per call' phrasing not removed"
    # Production = always, no high-diff gate
    assert "high_diff" not in body, "Production must not be high-diff gated"
    # top-level reconciliation contract + anti-boilerplate floor
    assert "codex_reconciliation" in body, "reconciliation contract missing"
    assert "codex_status" in body, "codex_status field missing"
    assert "codex_finding_ref" in body, "anti-boilerplate finding-reference floor missing"
    assert "codex_skip_reason" in body, "loud-skip reason field missing"


def test_plan_validator_side_high_diff_gated(tmp_path: Path) -> None:
    """Side plan-validator: mandatory iff high-diff, envelope preserved (ADR-002/003 matrix)."""
    rendered = _render_agent_files(tmp_path, enabled=True, preset=Preset.SIDE)
    body = rendered["plan-validator"]
    assert "high_diff classify" in body, "Side must gate on the high-diff detector"
    assert "MUST" in body, "mandatory-on-high-diff phrasing missing"
    assert _OPTIONAL_TITLE not in body, "plan-validator must not use the Optional title"
    # envelope still present on Side
    assert "codex_reconciliation" in body, "reconciliation contract missing on Side"
    assert "codex_status" in body, "codex_status field missing on Side"


def test_array_reviewers_unchanged_when_enabled(tmp_path: Path) -> None:
    """code-reviewer + consensus-arbiter keep opt-in MAY (deferred to follow-up PLAN)."""
    rendered = _render_agent_files(tmp_path, enabled=True)
    for agent in _ARRAY_REVIEWERS:
        body = rendered[agent]
        assert _OPTIONAL_TITLE in body, f"{agent} lost its opt-in Optional section"
        assert _OPT_IN_PHRASE in body, f"{agent} opt-in phrasing changed unexpectedly"
        # the plan-validator reconciliation ENVELOPE must NOT leak into the array
        # reviewers. (`codex_status` alone is no longer a clean marker — it is now
        # also a shared skip-receipt ledger field; `codex_reconciliation` is the
        # distinctive envelope key — ADR-002/005 of PLAN-crossmodel-codex-gaps.)
        assert "codex_reconciliation" not in body, f"reconciliation envelope leaked into {agent}"
        assert _MANDATORY_TITLE not in body, f"Required title leaked into {agent}"


def test_codex_recipe_has_no_invalid_ask_for_approval_flag(tmp_path: Path) -> None:
    """`codex exec` rejects --ask-for-approval (interactive-only); recipe must not emit it.

    Regression guard for PLAN-codex-exec-ask-for-approval-flag-invalid: codex-cli
    0.133.0 errors `unexpected argument '--ask-for-approval'` on the FIRST recipe
    line, so the second opinion silently skips. The valid isolation flag is
    `--sandbox read-only` (kept); `exec` is non-interactive — no approval flag applies.
    """
    rendered = _render_agent_files(tmp_path, enabled=True)
    for agent in _ALLOW_LISTED:
        body = rendered[agent]
        assert "--ask-for-approval" not in body, (
            f"{agent}: invalid `codex exec --ask-for-approval` flag present in recipe"
        )
        # the valid recipe is still intact
        assert "codex exec" in body, f"{agent}: codex exec recipe missing"
        assert "--sandbox read-only" in body, f"{agent}: --sandbox read-only flag missing"
