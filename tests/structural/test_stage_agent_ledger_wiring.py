"""P3 exit criteria 2-4 — the ledger is actually WIRED, on every target.

`test_stage_agent_ledger.py` proves the writer works. That test passes with zero wiring:
a writer nothing calls produces a zero-row denominator, and stage 2 then reads "the second
validator pass never changed a verdict" from an empty file. R3 in the PLAN names this as
the medium-likelihood, high-impact risk of this phase.

**Exit criterion 3 is the subtle one.** The expected dispatch count is derived from the
rendered *dispatch sites* — the `Task(subagent_type=...)` blocks — and never from the emit
lines or the ledger. A count taken from the emit lines would say "every emit line has an
emit line", which is true of a template with none of either.
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
from harness_maker.stage_agent_ledger import DISPATCH_FAILED, DISPATCH_SKIPPED
from harness_maker.synthesize import synthesize

_EMIT = re.compile(r"hm stage_agent_ledger emit\b")
_PERSIST = re.compile(r"hm stage_agent_ledger persist-payload\b")

#: INDEPENDENT source for the expected count (exit 3): the agent-dispatch sites themselves.
_DISPATCH_SITE = {
    "plan-validator": re.compile(r'subagent_type="plan-validator"'),
    "test-reviewer": re.compile(r'subagent_type="test-reviewer"'),
}

_STAGE_MARKERS = {
    "plan": "### Step 4 — Plan validation",
    "execute": "#### Phase A.5 — test-reviewer gate",
    "review": "### Step 3.4 — Stamp a stable `id`",
}


@cache
def _render_root() -> Path:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-ledger-wiring-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


@cache
def artifacts_for(stage: str) -> dict[str, str]:
    """Every rendered document inlining `stage`, discovered by content, not by path."""
    marker = _STAGE_MARKERS[stage]
    return {
        str(p.relative_to(_render_root())): text
        for p in sorted(_render_root().rglob("*.md"))
        if marker in (text := p.read_text(encoding="utf-8"))
    }


@pytest.mark.parametrize("stage", sorted(_STAGE_MARKERS))
def test_each_stage_is_discovered_on_all_three_targets(stage: str) -> None:
    """Positive control — every wiring assertion below is vacuous over an empty corpus.

    The codex family is the one a claude-only fixture cannot see, and it is a separate
    synthesis path; a wiring edit that missed it would be invisible without this.
    """
    found = artifacts_for(stage)
    assert f".claude/commands/hm/{stage}.md" in found
    assert f".claude/stages/{stage}.md" in found
    assert f".agents/skills/hm-{stage}/SKILL.md" in found


@pytest.mark.parametrize(
    ("stage", "agent"), [("plan", "plan-validator"), ("execute", "test-reviewer")]
)
def test_every_dispatch_site_is_accompanied_by_an_emit_line(stage: str, agent: str) -> None:
    """Exit 2 + exit 3. The expected count comes from the DISPATCH sites, not the emits."""
    for name, text in artifacts_for(stage).items():
        expected = len(_DISPATCH_SITE[agent].findall(text))
        assert expected >= 1, f"{name}: no {agent} dispatch site — the independent source is empty"
        # Compare the COUNTS, not mere presence. An earlier version computed `expected` and
        # then asserted only `_EMIT.search(...)`, so a second dispatch site added with no
        # ledger write still passed — the independent source was gathered and discarded.
        emits = len(_EMIT.findall(text))
        assert emits >= expected, (
            f"{name}: {expected} {agent} dispatch site(s) but only {emits} emit line(s) — "
            "a dispatch with no ledger write is a hole in the stage-2 denominator"
        )
        assert f"--agent {agent}" in text, f"{name}: emit line does not name {agent}"
        assert f"--stage {stage}" in text, f"{name}: emit line does not name stage {stage}"


def test_the_review_stage_persists_reviewer_payloads() -> None:
    """ADR-006 part 2 — the artifact whose absence made the replay check unimplementable."""
    for name, text in artifacts_for("review").items():
        assert _PERSIST.search(text), f"{name}: no payload persistence — replay stays impossible"


@pytest.mark.parametrize("stage", ["plan", "execute"])
def test_the_launch_failure_path_is_documented_as_a_row(stage: str) -> None:
    """A dispatch that never ran must not be silence.

    Silence makes an unavailable validator indistinguishable from an approving one — and
    `plan.md.j2` explicitly tells the model to self-review in the validator's place, so this
    path is reachable by design rather than only by accident.
    """
    for name, text in artifacts_for(stage).items():
        assert DISPATCH_FAILED in text or DISPATCH_SKIPPED in text, (
            f"{name}: the launch-failure path writes no row"
        )


@pytest.mark.parametrize("stage", ["plan", "execute"])
def test_the_emit_guidance_forbids_zero_for_unmeasured_duration(stage: str) -> None:
    """The null-vs-zero lesson has to reach the CALLER, not only the schema.

    `duration_ms` is nullable, so nothing rejects a `0` — the schema cannot tell an
    instant dispatch from an unmeasured one. Only the instruction can, and these rows are
    append-only, so a caller that defaults to `0` poisons the latency series permanently.
    """
    for name, text in artifacts_for(stage).items():
        assert re.search(r"do not pass `0`|never pass `0`", text, re.I), (
            f"{name}: nothing tells the caller to omit an unmeasured duration"
        )


def test_both_stages_share_one_ledger_file() -> None:
    """ADR-004 chose one file with discriminators over per-domain files.

    Asserted because the natural drift is a second file: it looks tidier and silently
    halves every cross-agent aggregation.
    """
    for stage in ("plan", "execute"):
        for name, text in artifacts_for(stage).items():
            assert "stage_agent_ledger emit" in text, f"{name}: not using the shared writer"
            # A second writer module is how the "one file" decision gets undone quietly.
            assert not re.search(r"hm \w*_ledger emit", text.replace("stage_agent_ledger", "")), (
                f"{name}: a second ledger writer appeared alongside the shared one"
            )
