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


