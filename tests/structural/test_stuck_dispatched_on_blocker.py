"""The `stuck` agent is dispatched by the stage that blocks — not merely installed.

`stuck` names its own triggers in its body ("`/hm:execute` Phase A.5 retry exhaust", Phase D
unfixable, ADR conflict) while **no stage template dispatched it**: `grep -r stuck
templates/stages/` returned zero. So `/hm:execute` halted on an exhausted A.5 budget with the
merged lens verdict and nothing else, and the agent written to name the binding constraint behind
that verdict never ran. Observed 2026-08-17 on a Codex `/hm:execute` that stopped at A.5 with two
blockers and no unblock path.

**The two load-bearing assertions pin relations — locus and order.** The fact about the document
is a dispatch SITE for `agent_type="stuck"` sitting inside the blocker region and ahead of the
instruction to surface; dispatch-after-surface is the halt this change removes, wearing the
vocabulary of the fix. The remaining assertions (brief contents, advisory wording) are content
checks over that region and are labelled as such — an earlier docstring claimed the file never
checks for a token, which was false of two of its own five tests.

**The order assertion reads on `_DISPATCH_STUCK`, not on a bullet that promises a dispatch.**
The first draft compared the *bullet* containing the words "Dispatch `stuck`" against the surface
bullet, and was green on a template whose actual fenced call sat six lines BELOW the surface
instruction — the precise configuration the paragraph above says it rejects. A proxy for the
subject is not the subject.
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

_BLOCKER = "If a PLAN phase blocks"

#: Runtime-agnostic. Claude Code dispatches with `Task(subagent_type=…)`, Codex with
#: `spawn_agent(agent_type=…)`; a pattern naming only the first counts ZERO on every Codex
#: artifact and reports a missing dispatch where the dispatch is spelled in the other runtime's
#: vocabulary (the lesson `test_multi_lens_a5._DISPATCH` already paid for).
_DISPATCH_STUCK = re.compile(r'(?:Task\(subagent_type|spawn_agent\(agent_type)="stuck"')

#: Everything `stuck` needs to name a binding constraint rather than restate the symptom. The
#: trigger name is what routes its Step 2; the failure output is what it reasons over.
_BRIEF_MUST_NAME = ("Phase A.5", "Phase D", "ADR conflict", "PLAN")


@cache
def _render_root() -> Path:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-stuck-dispatch-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


@cache
def _bodies() -> dict[str, str]:
    """Every rendered document carrying the blocker path, discovered by content, not by path.

    Path-based discovery would silently miss the codex family, which is a separate synthesis
    path — and Codex is the runtime the reported halt happened on.
    """
    found = {
        str(p.relative_to(_render_root())): text
        for p in sorted(_render_root().rglob("*.md"))
        if _BLOCKER in (text := p.read_text(encoding="utf-8"))
    }
    assert found, "no rendered document carries the blocker path — every assertion below is vacuous"
    return found


def test_all_three_targets_carry_the_blocker_path() -> None:
    """Positive control. Without it every assertion here is silently claude-only."""
    for expected in (
        ".claude/commands/hm/execute.md",
        ".claude/stages/execute.md",
        ".agents/skills/hm-execute/SKILL.md",
    ):
        assert expected in _bodies(), f"{expected} does not carry the blocker path"


def _blocker_region(text: str) -> str:
    """The blocker path, from its opening line to the next heading that follows it."""
    start = text.index(_BLOCKER)
    rest = text[start:]
    end = re.search(r"^#{2,6} ", rest, re.M)
    return rest if end is None else rest[: end.start()]


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_the_blocker_path_dispatches_stuck(name: str) -> None:
    """One dispatch, inside the blocker region.

    Region-scoped on purpose: a dispatch anywhere else in the document (say, in the A.5 retry,
    which still owns two rounds of its own) does not make the terminal halt escalate.
    """
    hits = _DISPATCH_STUCK.findall(_blocker_region(_bodies()[name]))
    assert len(hits) == 1, (
        f"{name}: {len(hits)} `stuck` dispatch site(s) in the blocker region, expected 1 — "
        "an installed-but-never-dispatched agent is how this stage came to halt with a symptom "
        "and no unblock path"
    )


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_stuck_is_dispatched_before_the_stage_surfaces(name: str) -> None:
    """Order, measured on the DISPATCH SITE — the thing the executor actually runs.

    Surfacing first ends the turn, so an escalation produced afterwards reaches nobody. The
    comparison is offset-based and both operands are located by their own pattern: a bullet that
    merely promises "dispatch before surfacing" is not evidence that the call precedes the
    surface step, and a gate keyed on that bullet passed a template where it did not.
    """
    region = _blocker_region(_bodies()[name])
    site = _DISPATCH_STUCK.search(region)
    assert site is not None, f"{name}: no `stuck` dispatch site in the blocker region"

    # `Surface` must be the item's OPENING verb. A looser `.*[Ss]urface` also matched the
    # dispatch item's own "before you surface anything", counting the same instruction twice and
    # reddening a correct document — the false-RED direction the tests lens warned about.
    surface = [m.start() for m in re.finditer(r"^\s*(?:\d+\.|-)\s+Surface\b", region, re.M)]
    assert len(surface) == 1, (
        f"{name}: {len(surface)} surface instruction(s), expected exactly 1 — the count is what "
        "keeps this anchor honest, since a document that drops the surface step must go red"
    )
    assert site.start() < surface[0], (
        f"{name}: the dispatch site sits AFTER the surface instruction — the stage would report "
        "the blocker and end the turn before the escalation it is supposed to carry exists"
    )


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_the_brief_carries_the_trigger_and_the_failure_output(name: str) -> None:
    """`stuck` Step 1 reads the failure output and Step 2 routes on which trigger fired.

    A bare "we are blocked" brief makes it re-derive both from the PLAN, which is the analysis
    it was dispatched to do on top of them, not instead of them.
    """
    region = _blocker_region(_bodies()[name])
    line = next((ln for ln in region.splitlines() if _DISPATCH_STUCK.search(ln)), None)
    assert line is not None, f"{name}: no `stuck` dispatch line in the blocker region"
    missing = [t for t in _BRIEF_MUST_NAME if t not in line]
    assert not missing, f"{name}: the `stuck` brief names none of {missing!r}"
    # The property is the HANDOVER, not one spelling of it: the brief has been compacted once
    # already, and a literal-only check would have failed on wording that still hands the output
    # over. Both accepted forms name the output that ENDED the phase, which is what Step 1 reads.
    assert re.search(r"failure output|output that ended the phase", line), (
        f"{name}: the brief does not hand over the failure output — `stuck` Step 1 lists it as "
        "required context and cannot reconstruct a test stderr from the PLAN"
    )


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_the_stage_does_not_act_on_the_recommendation(name: str) -> None:
    """`stuck` is advisory and read-only; an executor that applies Path A routes around the gate.

    The region must say so in the same breath as the no-silent-scope-change rule, because
    "dispatch an agent that proposes concrete moves" is otherwise an invitation to take one.
    """
    region = _blocker_region(_bodies()[name])
    assert re.search(r"advisory", region, re.I), (
        f"{name}: the blocker path does not call `stuck` advisory — nothing stops the stage from "
        "applying its recommendation and calling the phase unblocked"
    )
    # Two DIFFERENT properties, so they must not be satisfiable by one clause. An earlier
    # relaxation added `do NOT act on` here, and that phrase sits in the same sentence as
    # `advisory` — one clause then satisfied both conjuncts and no mutation could red this one
    # alone. The property here is that the decision is ROUTED somewhere, which is what stops an
    # executor from picking one of `stuck`'s 2-3 proposed paths itself.
    assert re.search(r"user (picks|decides)", region), (
        f"{name}: the blocker path never names who picks the unblock path — `stuck` proposes "
        "several, and an unowned decision is one the executor makes"
    )
