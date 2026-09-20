"""Phase 4 of PLAN-token-efficiency-autopilot-ux-speed — AC-006.

ADR-011 of the review work hoisted the cross-model call to run "concurrently with Pass 1", and
`run_in_background` appeared **nowhere** in this harness — so the foreground Bash blocked for up to
`CODEX_TIMEOUT_S=300` before the first reviewer was dispatched. This binds the wiring.

**Three of the four tests here are PRECONDITIONS, not the oracle.** AC-006's oracle is one real
`/hm:review` dispatch, and this AC's own text disqualifies a render-grep as proof: *fixture-shaped
output proves the validator and never the producer*. The oracle is the live test at the bottom of
this file, `skipif`'d on `INTEGRATION=1` **and** CLI presence (ADR-009) — outside that lane it
**skips**, which is not a pass.
The SPEC records the resulting status as MECHANISM LANDED, ORACLE UNVERIFIED rather than green.

**The stage guard is the load-bearing half.** `/hm:spec` must inject the adapted findings into
`spec-validator`'s prompt *before* dispatching it, so backgrounding there would leave nothing to
inject and the validator would silently become Claude-only. The dispatch partial is SHARED between
the two stages, so a single unguarded `run_in_background` would have broken the spec stage while the
review-stage test went green.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal

import pytest

from harness_maker.models import (
    InterviewAnswers,
    Preset,
    ProjectProfile,
    SecondOpinionConfig,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_BACKGROUND = "run_in_background: true"
_REFUSAL = "Do NOT background the invoker at this stage"


def _render_commands(
    tmp: Path, *, models: list[Literal["codex", "antigravity", "claude"]]
) -> dict[str, str]:
    render(
        synthesize(
            ProjectProfile(),
            InterviewAnswers(
                preset=Preset.PRODUCTION,
                targets=[Target.CLAUDE_CODE],
                second_opinion=SecondOpinionConfig(models=models),
            ),
        ),
        tmp,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    root = tmp / "commands" / "hm"
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(root.glob("*.md"))}


@pytest.fixture(scope="module")
def models_on(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return _render_commands(tmp_path_factory.mktemp("on"), models=["codex"])


@pytest.fixture(scope="module")
def models_off(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return _render_commands(tmp_path_factory.mktemp("off"), models=[])


def test_ac_006_the_review_render_backgrounds_the_invoker(models_on: dict[str, str]) -> None:
    """Precondition, not proof: the review stage must carry the backgrounding instruction."""
    review = models_on["review"]

    assert _BACKGROUND in review, "the review render does not tell the model to background the call"
    assert _REFUSAL not in review, "the review render carries the spec stage's refusal"


def test_ac_006_the_spec_render_refuses_to_background(models_on: dict[str, str]) -> None:
    """The stage guard, from the other side — and this is the half a shared partial would break.

    `/hm:spec` consumes the findings in its very next step (the `spec-validator` dispatch injects
    them), so a backgrounded call there has nothing to inject. An unguarded `run_in_background` in
    the shared partial would satisfy the review test above and silently make spec validation
    Claude-only.
    """
    plan = models_on["spec"]

    assert _REFUSAL in plan, "the spec render does not refuse to background"
    assert _BACKGROUND not in plan, "the spec render tells the model to background the call"


def test_ac_006_the_wiring_sits_inside_the_models_gate(models_off: dict[str, str]) -> None:
    """The instruction must not ship into a harness with no model enabled — asserted STRUCTURALLY.

    The render-level version of this claim (`_BACKGROUND not in models_off["review"]`) is kept below
    as a cheap sanity arm, but it is **not** what this test rests on, because I could not construct
    a mutation that makes it fail: byte-zero is enforced twice over — the caller wraps the include
    in `{%- if config.second_opinion and config.second_opinion.models %}` (`review.md.j2`) and the
    partial re-checks `{%- if _models %}` — and removing both still produced no leak. A test whose
    failure I cannot demonstrate proves nothing, which is the whole defect class this unit removes.

    So the load-bearing assertion is on the template SOURCE: the review block must appear AFTER the
    partial's `{%- if _models %}` line. That has a demonstrated killer — hoisting the block above
    that line turns this red — so it is a guard rather than a decoration.
    """
    partial = (
        Path(__file__).parents[2]
        / "src"
        / "harness_maker"
        / "templates"
        / "agents"
        / "_partials"
        / "second_opinion_dispatch.md.j2"
    ).read_text(encoding="utf-8")

    gate_at = partial.index("{%- if _models %}")
    review_block_at = partial.index("{%- if second_opinion_stage == 'review' %}")
    plan_block_at = partial.index("{%- if second_opinion_stage == 'spec' %}")

    assert review_block_at > gate_at, "the review backgrounding block escaped the models gate"
    assert plan_block_at > gate_at, "the spec refusal block escaped the models gate"

    # cheap sanity arm, deliberately not the load-bearing one (see the docstring)
    for name in ("review", "spec"):
        assert _BACKGROUND not in models_off[name]
        assert _REFUSAL not in models_off[name]


@pytest.mark.skipif(
    os.environ.get("INTEGRATION") != "1",
    reason=(
        "ADR-009: the live cross-model dispatch runs under INTEGRATION=1, not the PR gate. "
        "Re-gated 2026-09-12 — the previous guard keyed on CLI presence ALONE, so this test "
        "unskipped and failed on every ordinary suite run in any developer environment that "
        "happened to have `codex` or `agy` installed. That is the PR gate by another route, "
        "which is the thing ADR-009 decided against."
    ),
)
@pytest.mark.skipif(
    shutil.which("codex") is None and shutil.which("agy") is None,
    reason=(
        "AC-006's oracle needs one REAL cross-model dispatch and no second-opinion CLI is "
        "installed. This test SKIPS rather than passes: the SPEC records AC-006 as "
        "MECHANISM LANDED, ORACLE UNVERIFIED, and a render-grep is disqualified as proof by the "
        "AC's own text."
    ),
)
def test_ac_006_a_live_review_overlaps_the_fan_out() -> None:
    """THE ORACLE. Deliberately unimplemented rather than faked.

    Writing a mocked version of this would produce a green that means nothing — precisely the
    failure `[wiki:architecture] narrative-output-needs-explicit-envelope` records, where render
    greps, unit tests and SHA pins all passed while the behaviour was absent. The honest artifact is
    a test that cannot run here and says why, so the gap is visible to the next reader instead of
    being papered over.

    What it must assert: in one real `/hm:review` on a non-empty diff with `second_opinion.models`
    non-empty, the invoker's start timestamp precedes the completion of Pass 1's reviewer fan-out.

    **What blocks writing it is not the CLI — that was the original guess, and it is wrong.**
    Both CLIs were present on 2026-09-12 and the oracle still could not be written, because
    *nothing durably records when the fan-out completed*:

    * the invoker's start IS derivable — `second-opinion.jsonl` carries `ts` plus `duration_s`;
    * the fan-out's completion is NOT. `.hm-lens-results/<slug>/<run>/<round>/*.json` is written
      inside the task worktree under a gitignored path, so `task-land` destroys it; and
      `stage-agents.jsonl` carries no per-lens dispatch row (two full review runs that day left
      `confirmation-pass` rows and nothing else).

    So closing AC-006 needs a *producer* first — the review stage emitting a per-lens row — and
    that is a template change to the one stage `/hm:loop` pays for five times, against an
    `_ATOMIC_RATCHET["review"]` ceiling whose single ADR-011 carve-out is already spent. It is
    therefore its own unit of work, not a line in this file.

    **This alarm is developer-manual-only, and no CI lane fires it.** `ci.yml` never sets
    `INTEGRATION`; `nightly.yml` and `release.yml` set it only around
    `tests/integration/test_fresh_install_readiness.py`, so nothing collects this file with the
    variable set. Setting the variable would not help either: no lane that could run this file
    has a second-opinion CLI, so the second guard below would skip it. (Not "the runners have no
    CLI" — `ci.yml`'s `install-cmd-regression` job installs a pinned `codex` for its own advisory
    test. That job is not this one.) Before the re-gate, any developer with
    a CLI hit this failure on an ordinary suite run; now it takes a CLI *and* `INTEGRATION=1`.
    That is a weaker alarm, accepted because the stronger one was failing ordinary suite runs in
    every such environment, which is what ADR-009 decided against. The durable record of the gap
    is this docstring and the PLAN entry, not a gate — so do not read a green suite as evidence
    that AC-006 is closed.
    """
    pytest.fail(
        "AC-006's oracle is not implemented. INTEGRATION=1 and a CLI are both present, so the "
        "environment can host a live dispatch — but the fan-out completion signal it must "
        "compare against still has no durable producer (see this test's docstring)."
    )
