"""PLAN-bench-study-adoption Phase 4 — the canary is wired at every site, on both branches.

Two things make these more than presence-greps.

**Six literal lines, three logical sites.** `review.md.j2` invokes `hm lens_coverage check` at
Step 3, the Auto-Fix Loop re-check and the confirmation pass — and each is rendered twice,
behind `{% if is_codex %}` / `{% else %}`. An implementer counting to three edits the Claude
branch of each and leaves all three Codex renders unflagged. CLAUDE.md documents that exact
incident: every Codex file was generated with `is_codex=False` for months, the templates and the
artifacts both read as correct, and only the render CONTEXT was wrong. A Claude-branch assertion
cannot see it, so both branches are counted here.

**A re-check without the flags would readmit a lens the first check rejected.** That is why
every site must carry them, not just the first.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

# Anchored to an INVOCATION, not to the words. The unanchored form matched
# `review.md.j2:744` — the prose sentence "Whenever `hm lens_coverage check` reports
# `blocks_approval: true`" — which sits outside every `is_codex` fence and therefore renders
# into BOTH bodies. A fourth match carrying neither flag made both render tests unsatisfiable
# by any correct implementation, and the only ways to green were to mangle that sentence into
# holding CLI flags or to delete it. Phase A.5 round 1 caught it.
_CALL = re.compile(r'(?:^!|Bash\(")[^\n]*hm lens_coverage check[^\n]*', re.M)


def _profile(preset: Preset) -> ProjectProfile:
    return (
        ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
        if preset == Preset.SIDE
        else ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    )


@cache
def _root(preset: Preset) -> Path:
    profile = _profile(preset)
    answers = interview(profile, autoloop_mode=True)
    # Codex is requested explicitly: the `is_codex` half of this module is the point, and the
    # synthesized default does not include the target, so a fixture without it would leave the
    # Codex arm asserting nothing — while looking green.
    answers.targets = [Target.CLAUDE_CODE, Target.CODEX]
    bp = synthesize(profile, answers, preset=preset)
    out = Path(mkdtemp(prefix="hm-repo-probe-"))
    # Render INTO `.claude/`, not into the bare tempdir: the Codex assets are written relative
    # to the output directory's PARENT, so a bare-tempdir render puts `.agents/` outside the
    # fixture entirely and the Codex arm reads a path that cannot exist.
    render(bp, out / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return out


def _review(preset: Preset) -> str:
    return (_root(preset) / ".claude" / "commands" / "hm" / "review.md").read_text(encoding="utf-8")


def _codex_review(preset: Preset) -> str:
    return (_root(preset) / ".agents" / "skills" / "hm-review" / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_the_claude_render_has_three_coverage_calls_and_all_carry_the_flags() -> None:
    """Non-emptiness first: `all()` over an empty list is True, so the count is asserted."""
    calls = _CALL.findall(_review(Preset.PRODUCTION))
    assert len(calls) >= 3, calls
    for c in calls:
        assert "--diff-files" in c, c
        assert "--rev" in c, c


def test_the_codex_render_has_its_own_calls_and_all_carry_the_flags() -> None:
    """The half a Claude-branch test cannot see. CLAUDE.md's `is_codex` incident, avoided."""
    calls = _CALL.findall(_codex_review(Preset.PRODUCTION))
    assert len(calls) >= 3, calls
    for c in calls:
        assert "--diff-files" in c, c
        assert "--rev" in c, c


def test_production_asks_every_lens_for_a_probe() -> None:
    assert "repo_probe" in _review(Preset.PRODUCTION)


def test_production_tells_the_main_loop_to_transcribe_it() -> None:
    """The agent returns it; the MAIN LOOP writes the result file (Step 3's existing contract).

    A render that asks the reviewer for a probe but never says to carry it into the file it
    writes produces probes that exist only in a transcript nothing reads.
    """
    body = _review(Preset.PRODUCTION)
    anchor = 'adding a `"lens"` key'
    assert body.count(anchor) == 1, "the Step 3 anchor must identify the section, not a mention"
    step3 = body.split(anchor, 1)[1].split("\n### ", 1)[0]
    assert "repo_probe" in step3


@pytest.mark.parametrize("part", ["repo_probe", "--diff-files", "--rev"])
def test_side_carries_none_of_it(part: str) -> None:
    """ADR-005 gates on the preset, and ABSENCE is the half that proves the gate.

    A presence-only pair passes identically on a template that renders the block
    unconditionally — and on Side that block would make every review permanently unapprovable,
    because Side reviewers correctly emit no probe.
    """
    assert part not in _review(Preset.SIDE)


def test_the_reviewer_contract_lives_outside_the_per_finding_schema() -> None:
    """`repo_probe` is a TOP-LEVEL return field, not a per-finding one.

    `finding_schema.md.j2` is Contract-Boundary-protected precisely because editing it would
    put the probe on every finding — one canary per defect found, none at all for a lens that
    found nothing, which is the case the canary most needs to cover.
    """
    schema = (Path("src/harness_maker/templates/agents/_partials/finding_schema.md.j2")).read_text(
        encoding="utf-8"
    )
    assert "repo_probe" not in schema


def test_every_reviewer_agent_carries_the_contract() -> None:
    """All four backing agents, not just `code-reviewer`.

    Tool grants are per-agent and the seven lenses are served by four agents, so a contract
    added to one leaves the other three unable to answer — and their lenses then fail the
    check for a reason that is the harness's fault, not the model's.

    **Derived from `LENS_DISPATCH`, not hand-listed.** The literal tuple this replaces was
    factually correct on the day it was written, which is exactly how this repo's
    most-recurring failure class looks before it fires: an eighth lens backed by a fifth agent
    would leave that agent's contract unchecked while this test kept passing. Three previous
    instances were each fixed with a better hand list, and all three lists were wrong later.
    """
    from harness_maker.conditional_router import LENS_DISPATCH

    backing = {agent for agent, _ in LENS_DISPATCH.values()}
    assert len(backing) >= 4, backing  # non-emptiness: `all()` over {} is True
    agents = _root(Preset.PRODUCTION) / ".claude" / "agents"
    for name in sorted(backing):
        body = (agents / f"{name}.md").read_text(encoding="utf-8")
        assert "repo_probe" in body, name


def test_the_confirmation_pass_re_derives_its_own_diff_file_list() -> None:
    """Round-1 review finding: `probe_flags` is template-scope, so all three sites embed the
    ONE mktemp path written in Step 3.

    The confirmation pass redefines the diff as `review_base..<freeze commit>` — the whole
    review, including every auto-fix round's edits. Reusing round 1's list means a lens quoting
    a file the fixer edited in round 2 passes as out-of-diff evidence, on any review that
    needed a repair round. Asserted on the pass's own section so a fix elsewhere cannot satisfy
    it by accident.
    """
    body = _review(Preset.PRODUCTION)
    section = body.split("Step C2", 1)[1].split("### Step C3", 1)[0]
    assert "Re-derive" in section
    assert "review_base" in section


def test_side_does_not_carry_the_re_derivation_note() -> None:
    """ADR-005 again: Side runs no probe check, so an instruction to feed it a list is noise."""
    assert "Re-derive" not in _review(Preset.SIDE)
