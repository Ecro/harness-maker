"""The critic runs once, and its verdict reaches nothing that can gate on it.

Replaces `test_render_plan_revalidation.py` (SPEC-plan-stage-absorption). That file guarded
`/hm:plan` Step 4.5 — a **terminal re-validation pass** over the whole PLAN, recorded as
`validator_outcome: MAJOR_REVISION_TERMINAL` and handed to two readers who did opposite things
with it. Its own docstring carried the measurement that justified it: 12 `plan-validator`
episodes, not one reaching a clean verdict, with pass 2's criticals sometimes *created by* the
pass-1 fixes.

That measurement is why nothing here replaces it in kind. The full series is **0 APPROVED in
54 runs**, which does not say the critic is wrong — it says its discrimination is unmeasured.
ADR-004 therefore relocated it to `/hm:spec` as a **single advisory pass**: a second pass over a
loop that never converged buys findings, not release, and a gate whose discrimination nobody
has measured must not hold a release while it is being measured.

So the property under test inverted. It was "the terminal pass exists and is recorded as
terminal". It is now "there is exactly one pass, and no artifact carries a verdict that
anything downstream branches on". Both are falsifiable; this one fails the moment a second
dispatch or a blocking branch is added back.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.models import (
    InstrumentationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_STAGES = ("research", "spec", "execute", "review", "verify", "wrapup")


@pytest.fixture(scope="module")
def commands(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("single-pass")
    # `instrumentation.stage_agent_ledger` defaults to False, and the ledger block is gated on
    # it (`tests/render/test_instrumentation_axis.py` requires an OFF render to ship no emit
    # line at all). This file asserts the row EXISTS, so it has to render with the axis on —
    # otherwise it would pass on a harness that simply never records anything.
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE],
            instrumentation=InstrumentationConfig(stage_agent_ledger=True),
        ),
    )
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root / ".claude" / "commands" / "hm"


def _text(commands: Path, stage: str) -> str:
    return (commands / f"{stage}.md").read_text(encoding="utf-8")


def test_the_validator_is_dispatched_exactly_once_across_the_whole_surface(
    commands: Path,
) -> None:
    """Not just once in `spec.md` — once anywhere. A second home is a second pass."""
    total = sum(
        len(re.findall(r'subagent_type="spec-validator"', _text(commands, s))) for s in _STAGES
    )
    assert total == 1, f"spec-validator is dispatched {total} times across the rendered stages"


def test_the_single_pass_rule_is_stated_not_merely_true(commands: Path) -> None:
    """The rule has to be written down, not just satisfied by the current template.

    An earlier draft of this test banned the SUBSTRING "re-validation", which failed on the
    sentence that states the prohibition — an assertion bound to a word rather than to the
    dimension it names. The dispatch COUNT is what makes a second pass impossible, and that is
    asserted above. What is asserted here is different and not redundant: the reader is told
    there is one pass, so nobody reconstructs `/hm:plan` Step 4.5 from a template that merely
    happens to dispatch once.
    """
    spec = " ".join(_text(commands, "spec").lower().split())
    assert "one pass" in spec, (
        "the spec stage does not state the single-pass rule; ADR-004 allows one pass"
    )
    assert "no re-validation" in spec, (
        "the spec stage does not forbid a second pass; the loop it replaces was measured at "
        "0 APPROVED in 54 runs"
    )


def test_the_terminal_outcome_name_is_gone_from_the_surface(commands: Path) -> None:
    """`MAJOR_REVISION_TERMINAL` was unforgeable — it existed nowhere else. It should be gone.

    It named "a second pass ran and these findings survived it". With one pass there is no
    such state, and leaving the token behind would let a later reader reconstruct a two-pass
    contract that no longer exists.
    """
    for stage in _STAGES:
        assert "MAJOR_REVISION_TERMINAL" not in _text(commands, stage), (
            f"{stage}.md still names MAJOR_REVISION_TERMINAL, a two-pass-only outcome"
        )


def test_the_verdict_reaches_no_branch(commands: Path) -> None:
    """Advisory means nothing downstream reads it — assert the absence where it would live."""
    spec = _text(commands, "spec")
    approve_idx = spec.find("spec_machine approve")
    assert approve_idx > 0, "the spec stage no longer stamps acceptance at all"
    # The window immediately before the stamp is where a gate would have to sit.
    window = spec[max(0, approve_idx - 1500) : approve_idx]
    for banned in ("MAJOR_REVISION", "NEEDS_REVISION", "spec-validator"):
        assert banned not in window, (
            f"`{banned}` appears in the 1500 characters before the acceptance stamp — the "
            "critic's verdict must not stand between the DRI and the stamp"
        )


def test_the_dispatch_is_recorded_even_though_it_gates_nothing(commands: Path) -> None:
    """Advisory is not the same as invisible. The row is how discrimination gets measured."""
    spec = _text(commands, "spec")
    assert "--agent spec-validator" in spec
    assert "dispatch-failed" in spec, (
        "a dispatch that never launched writes no row, so an unavailable critic would be "
        "indistinguishable from an approving one — the same hole the predecessor documented"
    )
