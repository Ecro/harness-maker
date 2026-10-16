"""AC-007 / AC-008 / AC-009 — `spec-validator` critiques the SPEC and cannot gate it.

`plan-validator` returned APPROVED **0 times in 54 runs**. That is a gate with no measured
discrimination, not a critic with wrong findings — it has produced genuine defects. So the
absorption relocates it rather than deleting it, and the relocation carries three constraints
that exist because of that record:

- **one pass, no re-validation** — the loop it replaces never converged, so a second pass buys
  findings rather than release;
- **never blocks** — an unproven gate must not hold a release while it is being measured;
- **every dispatch is recorded** — that is the only way the next reader knows whether the
  discrimination ever showed up.

**Phase A.4 note.** `test_ac_007_approval_cannot_read_the_verdict` is a NEGATIVE invariant and
is vacuously green while no wiring exists between the verdict and the approval. It goes red the
moment someone makes approval conditional on the critic — the one change ADR-004 forbids. Its
RED positive siblings are the other four tests in this file, which fail until Phase 2 ships the
agent, its dispatch, its ledger row and the frontmatter field.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from harness_maker import spec_machine
from harness_maker.models import (
    InstrumentationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("spec-validator")
    # AC-008 asserts the ledger row EXISTS, and that block is gated on
    # `instrumentation.stage_agent_ledger`, which defaults to False. Rendering with the axis off
    # would make this pass on a harness that records nothing at all.
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE],
            instrumentation=InstrumentationConfig(stage_agent_ledger=True),
        ),
    )
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root / ".claude"


def _spec_stage(rendered: Path) -> str:
    return (rendered / "commands" / "hm" / "spec.md").read_text(encoding="utf-8")


def test_ac_007_dispatched_at_most_once(rendered: Path) -> None:
    """One dispatch site. A second one is the re-validation pass ADR-004 removed."""
    text = _spec_stage(rendered)
    sites = re.findall(r'subagent_type="spec-validator"', text)
    assert len(sites) == 1, (
        f"expected exactly one spec-validator dispatch in the rendered spec stage, found "
        f"{len(sites)}"
    )
    # Narrowed deliberately to DISPATCH sites. The stage's rationale for running a single pass
    # cites `plan-validator`'s 0-APPROVED-in-54 record, and an unrelated shipped partial names
    # it in an example; forbidding the string would forbid the documentation that makes the
    # single-pass rule legible. What must not survive is a dispatch.
    assert 'subagent_type="plan-validator"' not in text, (
        "the rendered spec stage still DISPATCHES `plan-validator` — the agent was relocated, "
        "not duplicated"
    )


def test_ac_007_approval_cannot_read_the_verdict(rendered: Path) -> None:
    """Approval is invariant under the critic's verdict — negative invariant, see module doc."""
    sig = inspect.signature(spec_machine.approve)
    offending = [p for p in sig.parameters if "verdict" in p or "validator" in p]
    assert not offending, (
        f"spec_machine.approve takes {offending}; a critic that can move the approval state is "
        "a blocking gate, which ADR-004 forbids while its discrimination is unmeasured"
    )
    source = inspect.getsource(spec_machine)
    assert "spec-validator" not in source, (
        "spec_machine names spec-validator; the approval path must not know it exists"
    )
    assert "spec_validator" not in source, (
        "spec_machine names spec_validator; the approval path must not know it exists"
    )
