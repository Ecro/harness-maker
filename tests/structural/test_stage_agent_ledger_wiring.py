"""P3 exit criteria 2-4 — the ledger is actually WIRED, on every target.

`test_stage_agent_ledger.py` proves the writer works. That test passes with zero wiring:
a writer nothing calls produces a zero-row denominator, and stage 2 then reads "the second
validator pass never changed a verdict" from an empty file. R3 in the PLAN names this as
the medium-likelihood, high-impact risk of this phase.

**Exit criterion 3 is the subtle one.** The expected dispatch count is derived from the
rendered *dispatch sites* — `Task(subagent_type=…)` on Claude, `spawn_agent(agent_type=…)`
on Codex — and never from the emit
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
from harness_maker.models import InstrumentationConfig, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.stage_agent_ledger import DISPATCH_FAILED, DISPATCH_SKIPPED
from harness_maker.synthesize import synthesize

_EMIT = re.compile(r"hm stage_agent_ledger emit\b")
_PERSIST = re.compile(r"hm stage_agent_ledger persist-payload\b")

#: INDEPENDENT source for the expected count (exit 3): the agent-dispatch sites themselves.
_DISPATCH_SITE = {
    # `(?:sub)?agent_type` — Claude dispatches with `Task(subagent_type=…)`, Codex with
    # `spawn_agent(agent_type=…)`. A pattern naming only the Claude spelling finds zero sites in
    # every Codex skill and reports the ledger as unwired where it is merely spelled otherwise.
    "plan-validator": re.compile(r'(?:sub)?agent_type="plan-validator"'),
    "test-reviewer": re.compile(r'(?:sub)?agent_type="test-reviewer"'),
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
    # ADR-011 made the ledger an opt-in axis that defaults OFF for a fresh install, so the
    # DEFAULT render legitimately carries none of the wiring this file exists to check. Pin
    # the axis ON here: the question is "when it is asked for, is it wired on every target?",
    # not "is it on by default?". Leaving it default would have turned all eleven assertions
    # green over an empty corpus — the exact vacuity the module docstring warns about.
    answers.instrumentation = InstrumentationConfig(stage_agent_ledger=True)
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
    """Exit 2 + exit 3. The expected count comes from the DISPATCH sites, not the emits.

    **`execute` counts ROUNDS, not dispatches** (PLAN-multi-lens-review-round ADR-007).
    Phase A.5 fans out to one `test-reviewer` per lens in a single message, and all three
    share one round: per-dispatch rows would collide on `(agent, stage, run-id, pass)` and
    leave `--terminal` unowned, which is the incoherence `coherence` reports. So the unit
    of the stage-2 denominator for A.5 is the round, and one emit line is correct.

    The independent source is not discarded — it is re-pointed. A hole would now be a round
    with no emit line, so the guard for `execute` is that the fan-out is accompanied by an
    emit line AND that the template says out loud which unit it is counting. Without that
    second half this degrades to the `_EMIT.search` presence check this file's own history
    records as insufficient.
    """
    rounds_not_dispatches = stage == "execute"
    for name, text in artifacts_for(stage).items():
        sites = len(_DISPATCH_SITE[agent].findall(text))
        assert sites >= 1, f"{name}: no {agent} dispatch site — the independent source is empty"
        # The independent source for a round-counted stage is the number of fan-out BLOCKS, not
        # the constant 1: hard-coding 1 would let a second, genuinely separate test-reviewer
        # round be added later with no emit line at all — the regression this guard exists for.
        #
        # A block is a FENCED region, not a run of adjacent lines. Line adjacency was tried and
        # is actively harmful: a blank line or a comment between the three Task( calls — a
        # formatting-only change that leaves the fan-out one message — would count 3 rounds and
        # demand 3 emit lines, and satisfying that produces exactly the per-dispatch rows
        # colliding on (agent, stage, run-id, pass) that ADR-007 forbids. A test must not be
        # able to drive the template into the state it guards against.
        lines = text.splitlines()
        fence_of: list[int] = []
        depth = 0
        for ln in lines:
            if ln.startswith("```"):
                depth += 1
            fence_of.append(depth)
        at = [i for i, ln in enumerate(lines) if _DISPATCH_SITE[agent].search(ln)]
        rounds = len({fence_of[i] for i in at})
        # Compare the COUNTS, not mere presence. An earlier version computed `expected` and
        # then asserted only `_EMIT.search(...)`, so a second dispatch site added with no
        # ledger write still passed — the independent source was gathered and discarded.
        emits = len(_EMIT.findall(text))
        expected = rounds if rounds_not_dispatches else sites
        assert emits >= expected, (
            f"{name}: {sites} {agent} dispatch site(s) in {rounds} fan-out block(s), unit="
            f"{'round' if rounds_not_dispatches else 'dispatch'}, expected >= {expected} emit "
            f"line(s) but found {emits} — an unrecorded {agent} run is a hole in the "
            "stage-2 denominator"
        )
        if rounds_not_dispatches:
            # Locus, not presence: the phrase must sit between the last dispatch line and the
            # emit line it governs. Searched over the whole document it goes inert the moment
            # the words appear anywhere — including in this very sentence, were it prose.
            window = "\n".join(lines[at[-1] :])
            head = window[: window.index("stage_agent_ledger emit")]
            assert "One row per **round**" in head, (
                f"{name}: A.5 fans out to {sites} dispatches but the emit guidance between the "
                "last dispatch and the emit line does not state that the row is per-ROUND — a "
                "reader would emit one row per lens, colliding on (agent, stage, run-id, pass) "
                "with no --terminal owner"
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


# ── F-C: the cap and the over-cap path are stated, not merely implied ─────────


def test_the_validator_pass_cap_is_stated_in_the_guidance() -> None:
    """`--pass <1|2>` encoded the cap in a placeholder and nothing enforced it.

    A third pass then ran (`msms-20260807-1`) with no instruction covering it, and the
    pre-registered aggregation — an equality on `== 2` — silently dropped the row.
    """
    for name, text in artifacts_for("plan").items():
        assert "The cap is 2 passes" in text, f"{name}: the pass cap is not stated"
        assert "--pass <1|2>" not in text, (
            f"{name}: the placeholder still implies the cap instead of the guidance stating it"
        )


def test_an_over_cap_pass_must_still_be_recorded_with_a_reason() -> None:
    """Dropping the row to keep the data tidy is the tempting wrong answer.

    An unrecorded pass is a serial barrier the latency figures charge to nobody, and without
    a reason the ledger cannot separate "the operator asked" from "the stage overran its own
    limit" — opposite remedies.
    """
    for name, text in artifacts_for("plan").items():
        assert re.search(r"still record it.*--reason", text, re.S), f"{name}: no over-cap rule"
        assert "Never drop the row" in text, f"{name}: dropping the row is not forbidden"


def test_exactly_one_terminal_row_per_run_is_stated() -> None:
    for name, text in artifacts_for("plan").items():
        assert re.search(r"[Ee]xactly one row per .* may carry `--terminal`", text), (
            f"{name}: the one-terminal-per-run invariant is not stated"
        )
