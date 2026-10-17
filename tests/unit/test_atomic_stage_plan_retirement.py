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
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harness_maker import interview
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import AtomicStage, AutonomyConfig, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_SURVIVING = ["research", "spec", "execute", "wrapup"]
#: Folded into execute / wrapup in 0.64.0 but still enum members for the retired autopilot CLI.
_FOLDED = ["review", "verify"]


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
    """The enum member is gone and the six members (four stages + two folded) are intact.

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
    assert set(values) == {*_SURVIVING, *_FOLDED}, f"the surviving stage SET drifted: {values}"
    assert not hasattr(AtomicStage, "PLAN"), "AtomicStage.PLAN is still importable"


def test_ac_004_default_pipeline_keeps_its_semantic_order() -> None:
    """The shipped default is the four rendered stages, and names no retired or folded one."""
    default = [s.value for s in AutonomyConfig().pipeline]
    assert default == _SURVIVING, f"the default pipeline order drifted: {default}"


_RETIRED_OR_FOLDED = ("plan", *_FOLDED)
_ADVISORY = "autonomy.pipeline names retired stage"


def _advisories(handler: _Collect) -> list[str]:
    return [m for m in handler.messages if _ADVISORY in m]


@st.composite
def _legacy_autonomy(draw: st.DrawFn) -> dict[str, object]:
    """A 0.62 block: any subsequence of the live stages with retired names spliced in."""
    base = [s for s in _SURVIVING if draw(st.booleans())]
    retired = draw(
        st.lists(st.sampled_from(_RETIRED_OR_FOLDED), min_size=1, max_size=3, unique=True)
    )
    pipeline = list(base)
    for name in retired:
        pipeline.insert(draw(st.integers(min_value=0, max_value=len(pipeline))), name)
    cap = st.one_of(st.none(), st.integers(min_value=1, max_value=500))
    return {
        "level": draw(st.sampled_from(["gated", "auto_safe", "ask"])),
        "pipeline": pipeline,
        "step_cap": draw(cap),
        "time_cap_min": draw(cap),
        "extra_deny": draw(
            st.lists(st.sampled_from(["Bash(rm -rf:*)", "Bash(terraform destroy:*)"]), unique=True)
        ),
        "autopilot_persistent": draw(st.booleans()),
    }


@given(legacy=_legacy_autonomy())
def test_ac_003_legacy_pipeline_drops_retired_names_once(legacy: dict[str, object]) -> None:
    """SPEC-retire-autopilot-remnants AC-003: order-preserving removal, nothing else moves."""
    raw = legacy["pipeline"]
    assert isinstance(raw, list)
    removed = [s for s in raw if s not in _RETIRED_OR_FOLDED]
    with _captured() as first:
        parsed = interview._parse_autonomy(legacy)

    assert [s.value for s in parsed.pipeline] == (removed or _SURVIVING)
    dumped = parsed.model_dump(mode="json")
    for key in ("level", "step_cap", "time_cap_min", "extra_deny", "autopilot_persistent"):
        assert dumped[key] == legacy[key], key
    assert len(_advisories(first)) == 1, first.messages

    with _captured() as second:
        again = interview._parse_autonomy(dumped)
    assert again == parsed
    assert _advisories(second) == [], "the migrated pipeline still triggers an advisory"


@pytest.mark.parametrize("preset", ["Side", "Production"])
def test_ac_005_migration_persists_through_a_render(tmp_path: Path, preset: str) -> None:
    """SPEC-retire-autopilot-remnants AC-005: the written harness.yaml, not the parsed object."""
    legacy = tmp_path / "legacy.yaml"
    legacy.write_text(
        "---\ngenerated_by: harness-maker\n---\n"
        f"preset: {preset}\nlocale: en\ntargets: [claude-code]\n"
        "autonomy:\n  level: auto_safe\n"
        "  pipeline: [research, spec, plan, execute, review, verify, wrapup]\n",
        encoding="utf-8",
    )
    answers = answers_from_harness_yaml(legacy)
    assert answers is not None
    out = tmp_path / "out"
    render(synthesize(ProjectProfile(), answers), out, freeze_time=DEFAULT_FREEZE_TIME)
    written = out / "harness.yaml"

    pipeline = load_harness_yaml(written)["autonomy"]["pipeline"]
    assert not set(_RETIRED_OR_FOLDED) & set(pipeline), pipeline
    with _captured() as handler:
        assert answers_from_harness_yaml(written) is not None
    assert _advisories(handler) == []
