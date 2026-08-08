"""ADR-011 — the `instrumentation` axis's reverse mapper and its absent case.

The absent case is the whole point. `[fail:design] absent-case = feature black hole`
(count:8) is this repo's most-recurring class, and this axis has the shape that produces
it: a key that did not exist in any harness.yaml rendered before today. If the absent
branch resolved to `false`, every existing project would silently stop contributing rows
on its next `--update` — and the cross-project denominator is not decoration, it is what
reversed the plan-validator verdict (harness-maker's own six rows said delete; the pooled
population said keep).

Note the direction is the OPPOSITE of `_parse_autonomy`'s, whose absent branch pins the
conservative `gated`. There, absent must not escalate the user's autonomy. Here, absent
must not revoke the maintainer's measurement. Same "absent means what?" question, opposite
answers, because the thing at risk is different.
"""

from __future__ import annotations

import logging

import pytest

from harness_maker.interview import _parse_instrumentation, answers_from_harness_yaml
from harness_maker.models import InstrumentationConfig, InterviewAnswers, Preset, ProjectProfile
from harness_maker.synthesize import synthesize


def test_the_class_default_is_off_for_a_fresh_install() -> None:
    """A NEW harness opts in; the absent-key case below is the opposite and deliberately so."""
    assert InstrumentationConfig().stage_agent_ledger is False


def test_absent_block_keeps_collecting_and_says_so(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="harness_maker.interview"):
        assert _parse_instrumentation(None).stage_agent_ledger is True
    assert any("instrumentation" in r.message for r in caplog.records), caplog.records


def test_explicit_false_is_honoured() -> None:
    assert _parse_instrumentation({"stage_agent_ledger": False}).stage_agent_ledger is False


def test_non_bool_falls_back_to_on_not_to_a_crash() -> None:
    """A hand-edited `stage_agent_ledger: "no"` must not take the whole load down."""
    assert _parse_instrumentation({"stage_agent_ledger": "no"}).stage_agent_ledger is True


@pytest.mark.parametrize("on", [True, False])
def test_round_trip_through_harness_yaml(tmp_path, on: bool) -> None:  # type: ignore[no-untyped-def]
    """synthesize → harness.yaml → answers_from_harness_yaml, both values."""
    from harness_maker.render import DEFAULT_FREEZE_TIME, render

    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            instrumentation=InstrumentationConfig(stage_agent_ledger=on),
        ),
    )
    render(bp, tmp_path / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    restored = answers_from_harness_yaml(tmp_path / ".claude" / "harness.yaml")
    assert restored is not None
    assert restored.instrumentation.stage_agent_ledger is on
