"""F1 — the mechanically decidable check runs before the judgment-based one.

Eleven Phase A.5 findings across two tasks were the single sentence "this test passes before the
implementation exists". Whether a test passes against the unmodified subject is decidable by
running it; spending a three-lens reviewer dispatch to decide it is the most expensive path this
stage offers. Phase A.4 moves that decision ahead of the dispatch.

These assertions are anchored to ORDER and to the brief's contents, because the defect is not
that the check is missing — Phase B always had it — but that it ran after the money was spent.
"""

from __future__ import annotations

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def execute_body(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("rendered-exec")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    render(synthesize(p, interview(p, autoloop_mode=True)), out, freeze_time=DEFAULT_FREEZE_TIME)
    f = out / "commands" / "hm" / "execute.md"
    assert f.is_file(), f"missing rendered command file: {f}"
    return f.read_text(encoding="utf-8")


def _heading(body: str, name: str) -> int:
    """Index of the phase HEADING, not the first mention of its name.

    `body.find("Phase A.5")` lands on the Communication Protocol sentence at the top of the
    document, which precedes every phase — so an order assertion built on it compares two
    prose mentions and is satisfied by any ordering. Caught by this file's own first run,
    which is the fifth time this weak-anchor class has appeared in this task.
    """
    i = body.find(f"#### {name}")
    assert i != -1, f"rendered execute command has no `#### {name}` heading"
    return i


def _phase_block(body: str, name: str, until: str) -> str:
    return body[_heading(body, name) : _heading(body, until)]


def test_the_screen_runs_before_the_reviewer_dispatch(execute_body: str) -> None:
    """Order is the whole point — Phase B has always screened, and always too late."""
    screen = _heading(execute_body, "Phase A.4")
    dispatch = _heading(execute_body, "Phase A.5")
    assert screen != -1, "no false-RED screen is rendered"
    assert dispatch != -1
    assert screen < dispatch, (
        "the false-RED screen renders after the reviewer gate, which is the ordering that "
        "made eleven findings cost a reviewer round each"
    )


def test_the_screen_names_both_dispositions_for_a_passing_test(execute_body: str) -> None:
    """A bare "all tests must fail" rule is wrong and would be worked around.

    Some passing tests are legitimate: a negative invariant is vacuously true while the
    construct it forbids does not exist. Measured this task — two such tests, each paired with a
    RED positive sibling. A screen that forbids them teaches the author to delete the invariant.
    """
    block = _phase_block(execute_body, "Phase A.4", "Phase A.5")
    assert "Fix it" in block, "the screen does not name the ordinary disposition"
    assert "vacuously true" in block, (
        "the screen does not admit the legitimate case, so it will be worked around"
    )
    assert "sibling" in block, (
        "a vacuous pass is only legitimate when a RED positive sibling forces the construct "
        "into existence; without that clause the justification path is a loophole"
    )


def test_the_screen_demands_read_counts_not_inferred_ones(execute_body: str) -> None:
    """The measured failure: a brief stated `24 failed, 3 passed` when the truth was 25/2.

    All three lenses were then told to find a third passing test that did not exist. The count
    came from eyeballing a progress string rather than reading the summary line.
    """
    block = _phase_block(execute_body, "Phase A.4", "Phase A.5")
    assert "Do not infer" in block


def test_the_brief_carries_the_screen_result(execute_body: str) -> None:
    """Without this the lenses rediscover what A.4 already decided, and the saving is zero."""
    block = _phase_block(execute_body, "Phase A.5", "Phase B")
    assert "A.4" in block, "the A.5 brief does not carry the screen's result"
    assert "MEASUREMENT" in block
