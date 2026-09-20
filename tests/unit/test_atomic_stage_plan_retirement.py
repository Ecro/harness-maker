"""AC-004 / IRR-002 — retiring `AtomicStage.PLAN` must not break an existing harness.

Every `harness.yaml` rendered before this change carries `plan` inside `autonomy.pipeline`.
Removing the enum member without a migration makes `AutonomyConfig.model_validate` reject the
whole block, and `_parse_autonomy`'s tolerant fallback then resets the user's level, caps AND
pipeline to defaults — silently. A project that had opted into `auto_safe` would find itself
back on `gated` with no message. That is why IRR-002 is `data migration`: the drop rewrites
user configuration in place and the original value is not recoverable afterwards.

The oracle is metamorphic and the relation is **idempotence**: the first load changes the
pipeline and says so exactly once; loading what that produced changes nothing and says
nothing. It holds regardless of how the drop is coded, so an implementation cannot satisfy it
by being read. The in-repo precedent for the shape is `guard_when`, retired the same way in
this same function, and the `codex_second_opinion` → `second_opinion` migration.

Logging is captured with a locally-attached handler rather than `caplog`, because a
function-scoped fixture under `@given` is re-entered per example and hypothesis rejects it.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from hypothesis import given
from hypothesis import strategies as st

from harness_maker import interview
from harness_maker.models import AtomicStage, AutonomyConfig

_SURVIVING = ["research", "spec", "execute", "review", "verify", "wrapup"]


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@contextmanager
def _captured() -> Iterator[_Collect]:
    """Messages the interview module logs, without touching global config."""
    handler = _Collect()
    logger = interview.logger
    previous_level, previous_propagate = logger.level, logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


def _retirement_lines(handler: _Collect) -> list[str]:
    """Lines that name the retirement — not every line the loader happens to emit."""
    return [m for m in handler.messages if "plan" in m.lower() and "pipeline" in m.lower()]


@given(
    position=st.integers(min_value=0, max_value=len(_SURVIVING)),
    level=st.sampled_from(["gated", "auto_safe", "ask"]),
)
def test_ac_004_legacy_pipeline_migrates_once(position: int, level: str) -> None:
    """`plan` in ANY position is dropped, the rest survives in order, one advisory is logged."""
    block = {
        "level": level,
        "pipeline": [*_SURVIVING[:position], "plan", *_SURVIVING[position:]],
    }
    with _captured() as handler:
        parsed = interview._parse_autonomy(block)

    assert [s.value for s in parsed.pipeline] == _SURVIVING, (
        "the surviving stages must keep their order and count; got "
        f"{[s.value for s in parsed.pipeline]}"
    )
    assert parsed.level == level, (
        "dropping a retired stage must not reset the user's level — that silent reset is the "
        "whole failure IRR-002 names"
    )
    lines = _retirement_lines(handler)
    assert len(lines) == 1, f"expected exactly one retirement advisory, got {lines}"


@given(
    position=st.integers(min_value=0, max_value=len(_SURVIVING)),
    level=st.sampled_from(["gated", "auto_safe", "ask"]),
)
def test_ac_004_second_load_is_silent(position: int, level: str) -> None:
    """Idempotence: what the first load produced loads clean and says nothing."""
    block = {
        "level": level,
        "pipeline": [*_SURVIVING[:position], "plan", *_SURVIVING[position:]],
    }
    with _captured() as first_handler:
        first = interview._parse_autonomy(block)
    # Bind the second load to a first load that ACTUALLY migrated. Without this the test is
    # vacuously green while no migration exists at all — "the second load is silent" is trivially
    # true when the first one was too, which is the false-RED Phase A.4 exists to catch.
    assert len(_retirement_lines(first_handler)) == 1, (
        "the first load did not emit a retirement advisory, so this test would be asserting "
        "silence about a migration that never happened"
    )
    migrated = {"level": level, "pipeline": [s.value for s in first.pipeline]}

    with _captured() as handler:
        second = interview._parse_autonomy(migrated)

    assert [s.value for s in second.pipeline] == [s.value for s in first.pipeline]
    assert _retirement_lines(handler) == [], (
        "the migrated harness.yaml still triggers an advisory — a warning that fires on every "
        "load is one users learn to ignore, which is how the next real one gets missed"
    )


def test_ac_004_atomic_stage_no_longer_admits_plan() -> None:
    """The enum member is gone and the six survivors are intact.

    Membership and ORDER are asserted separately on purpose. The enum's declaration order
    (`… WRAPUP, VERIFY`) is arbitrary; the pipeline's order (`… verify, wrapup`) is semantic.
    An earlier draft compared the enum against the pipeline order and failed on a difference
    that means nothing — an assertion not bound to the dimension its name claims.
    """
    values = [m.value for m in AtomicStage]
    assert "plan" not in values, (
        f"AtomicStage still admits `plan`: {values}. IRR-001 removes the stage; leaving the "
        "enum member keeps a pipeline entry that renders to nothing."
    )
    assert set(values) == set(_SURVIVING), f"the surviving stage SET drifted: {values}"
    assert not hasattr(AtomicStage, "PLAN"), "AtomicStage.PLAN is still importable"


def test_ac_004_default_pipeline_keeps_its_semantic_order() -> None:
    """The shipped default runs verify before wrapup, and no longer names `plan`."""
    default = [s.value for s in AutonomyConfig().pipeline]
    assert default == _SURVIVING, f"the default pipeline order drifted: {default}"
