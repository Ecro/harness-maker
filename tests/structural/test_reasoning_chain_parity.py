"""Reasoning-chain authority parity (PLAN-second-opinion-acceptance-gate ADR-008).

The interesting part is the direction. An earlier draft of this work treated the
`consensus-arbiter`'s 4-step chain as the divergence and planned to delete TRACE from it,
locking that in with a `no TRACE` grep. That was backwards: `_partials/reasoning.md.j2`
mandates four steps, `_partials/finding_schema.md.j2` specifies the emitted `reasoning`
field as the 4-step chain, and the arbiter says explicitly that it matches the partial. The
outliers were the CONSUMERS that compared three — review's Step 4b and `code-verifier`'s
own DROP rubric. So this module asserts the four-step shape at the two live consumer sites
and does NOT assert its absence anywhere.

Two sites remain 3-step and are deliberately out of scope: `plan-validator_body.md.j2` and
`test-reviewer_body.md.j2`. Neither is on the `/hm:review` acceptance path this work owns,
and editing the plan-validator's prose mid-task would have changed the artifact that was
validating the plan. They are named here so the next reader does not re-derive the
"single outlier" premise this test exists to correct.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_TEMPLATES = Path(__file__).parents[2] / "src" / "harness_maker" / "templates"

_FOUR_STEP_SOURCE = _TEMPLATES / "agents" / "_partials" / "reasoning.md.j2"
_LIVE_CONSUMERS = (
    _TEMPLATES / "stages" / "review.md.j2",
    _TEMPLATES / "agents" / "code-verifier_body.md.j2",
)
_ARBITER = _TEMPLATES / "agents" / "consensus-arbiter_body.md.j2"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_authority_really_mandates_four_steps() -> None:
    """Discrimination guard. Every assertion below is premised on the shared partial being
    the 4-step authority; if that premise ever flips, the rest of this module is wrong and
    should fail loudly rather than keep enforcing a stale direction."""
    body = _text(_FOUR_STEP_SOURCE).lower()
    for step in ("observe", "trace", "infer", "conclude"):
        assert step in body, f"the shared reasoning partial no longer names {step!r}"


@pytest.mark.parametrize("path", _LIVE_CONSUMERS, ids=lambda p: p.name)
def test_live_consumers_compare_the_four_step_chain(path: Path) -> None:
    """A consumer that compares three steps is comparing a shape its reviewers were never
    told to emit — findings arrive with `trace` populated and match no documented step."""
    body = _text(path)
    assert "TRACE" in body, f"{path.name} does not name the TRACE step"
    assert "three reasoning steps" not in body, f"{path.name} still gates on a 3-step chain"


def test_arbiter_calls_the_helper_with_its_real_signature() -> None:
    """`scope_aware_consensus` takes one argument. The 2-arg call in this prose could never
    have run — which is itself the tell that this agent is not on any live path."""
    body = _text(_ARBITER)
    assert "scope_aware_consensus(findings)" in body
    assert "reviewer_scopes)" not in body


def test_arbiter_states_that_review_does_not_invoke_it() -> None:
    """`scope-exempted` is documented here and absent from review's Step 4d table. Without
    this note the mismatch reads as a bug in one of the two surfaces."""
    assert "does not invoke this agent" in _text(_ARBITER)


def test_the_two_deferred_three_step_sites_are_still_the_only_ones() -> None:
    """Scope fence. If a THIRD 3-step site appears, the follow-up note in ADR-008 is no
    longer accurate and this test should force it to be revisited."""
    agents = (_TEMPLATES / "agents").glob("*_body.md.j2")
    three_step = sorted(p.name for p in agents if "OBSERVE → INFER → CONCLUDE" in _text(p))
    assert three_step == ["plan-validator_body.md.j2", "test-reviewer_body.md.j2"], (
        f"unexpected 3-step site set: {three_step}"
    )
