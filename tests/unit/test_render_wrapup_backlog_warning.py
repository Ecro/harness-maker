"""AC-003 — wrapup warns from its main loop when the open-proposal backlog reaches five.

ADR-004: the wrapup template must obtain the count from the proposals CLI and must NOT
describe a counting rule of its own. Stage templates are prose and cannot import Python, so a
template-side rule would be a second implementation of "what counts as open" — and the real
file has no per-proposal RESOLVED heading, so a plausible-looking prose rule would silently
disagree with the CLI.

ADR-006 (salvage): the call lives in the main-loop `### Steps 6 → 7.6` section. The source
task put it in Step 5.3, which runs inside `stage-delegate` whose prose never reaches the user
— a write-only warning, the defect this task exists to remove. The placement is therefore
asserted on RENDERED text, on the delegated and the default (no Step 0.5) render, and on both
worktree arms: a template-source assertion would pass a render that drops the paragraph.

The negative assertions are what make this non-vacuous: a template that adds the warning while
also spelling out a heading-matching rule, or that leaves the call inside the delegated span,
would pass a presence-only check.

A.4 (justified pass): `test_wrapup_still_renders_the_escalation_receipt` passes on the
unmodified template by design — it is a preservation guard that goes red the moment the new
paragraph displaces Step 5.3's receipt. Its RED positive sibling is
`test_wrapup_renders_backlog_warning_threshold`, which forces the paragraph into existence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import (
    DelegationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

WRAPUP = "commands/hm/wrapup.md"
CALL = "hm proposals summary"
#: The section's own halt rule — the call must precede it, or an unexpected exit above it
#: halts wrapup before the warning ever prints (codex P1 c16b57f0). Anchored on the clause
#: itself, not on the bare phrase: the new paragraph QUOTES "surface verbatim and halt" to
#: exempt its own call, so matching the phrase would find the paragraph's own sentence
#: (review 2f800768).
HALT_RULE = "Any other non-zero exit: surface verbatim and halt"
MAIN_LOOP_HEADING = "### Steps 6 "


def _flat(text: str) -> str:
    """Collapse whitespace before matching — these assertions are about content, not wrapping."""
    return " ".join(text.split())


def _render_wrapup(
    tmp_path: Path, *, stages: list[str] | None = None, feature_branch: bool = True
) -> str:
    # `feature_branch_workflow` is set explicitly: constructing InterviewAnswers directly
    # bypasses the preset extras, so the flag-gated sections would otherwise not render.
    answers = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE],
        delegation=DelegationConfig(stages=stages or []),
        worktree={"feature_branch_workflow": feature_branch},
    )
    render(synthesize(ProjectProfile(), answers), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return (tmp_path / WRAPUP).read_text(encoding="utf-8")


def test_wrapup_renders_backlog_warning_threshold(tmp_path: Path) -> None:
    body = _render_wrapup(tmp_path)
    assert CALL in body, "wrapup must ask the CLI for the backlog summary"
    flat = _flat(body)
    assert "5 or more" in flat, "the threshold must be stated explicitly"
    assert "Below 5, print nothing" in flat, "the below-threshold behaviour must be stated"
    assert "(oldest" in flat, "the warning line must carry the oldest open date (ADR-007)"
    assert "hm proposals list --open" in flat, "the warning must name the triage command"


def test_wrapup_warning_states_the_degrade_contract(tmp_path: Path) -> None:
    """ADR-004/007: degrade prints a reason; never halt, never a silent no-op.

    W1 (validator): the section ends in a halt rule covering every non-zero exit, and the
    pre-release dogfood harness lacks the verb — `hm` exits 2 with `unknown module`. Without an
    explicit exemption that certain failure reads as "halt".
    """
    flat = _flat(_render_wrapup(tmp_path))
    for required in (
        "Never halt",
        "never treat an error string as a count",
        "never skip silently",
        "A failure of this call is never a reason to halt",
    ):
        assert required in flat, f"degrade contract missing: {required!r}"


def test_wrapup_does_not_describe_its_own_counting_rule(tmp_path: Path) -> None:
    """A second implementation of 'what counts as open' is the failure ADR-004 forbids."""
    flat = _flat(_render_wrapup(tmp_path))
    at = flat.index(CALL)
    window = flat[max(0, at - 600) : at + 900]
    assert "do **not** describe a counting rule here" in window
    assert "count the `## Proposal:` headings" not in flat
    assert "grep -c" not in window


def test_wrapup_still_renders_the_escalation_receipt(tmp_path: Path) -> None:
    """The new paragraph must not displace Step 5.3's receipt (regression guard)."""
    assert "escalation: K entries at count>=3, P proposals written" in _render_wrapup(tmp_path)


@pytest.mark.parametrize("stages", [[], ["wrapup"]], ids=["default", "delegated"])
@pytest.mark.parametrize("feature_branch", [True, False], ids=["flag_on", "flag_off"])
def test_wrapup_backlog_check_runs_in_the_main_loop(
    tmp_path: Path, stages: list[str], feature_branch: bool
) -> None:
    """ADR-006: exactly one call, inside `Steps 6 → 7.6`, before that section's halt rule."""
    body = _render_wrapup(tmp_path, stages=stages, feature_branch=feature_branch)
    assert body.count(CALL) == 1, f"expected exactly one {CALL!r} call"
    at = body.index(CALL)
    section = body.index(MAIN_LOOP_HEADING)
    halt = body.index(HALT_RULE, section)
    assert section < at < halt, "the call must sit in Steps 6 → 7.6, above its halt rule"

    if stages:
        # Positive control: without Step 0.5 the "absent from the delegated span" check below
        # would pass vacuously — the default render has no dispatch block at all (validator W6).
        delegate = body.index("### Step 0.5")
        assert CALL not in body[delegate:section], "the call must not run inside the delegate"

    # The fenced block holding the call keeps a blank line on both sides — the `{%-` whitespace
    # control near the section head would otherwise glue it to its neighbours (validator S1).
    fence_open = body.rindex("```", 0, at)
    fence_close = body.index("```", at)
    assert body[fence_open - 2 : fence_open] == "\n\n", "no blank line before the call's fence"
    after = fence_close + len("```")
    assert body[after : after + 2] == "\n\n", "no blank line after the call's fence"
