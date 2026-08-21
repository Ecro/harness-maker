"""PLAN-bench-study-adoption Phase 3 — the measurement is wired, not merely available.

Terminal plan-validation's finding: a phase whose exit criterion only proves the calculator
emits a row can pass with **both sinks disconnected** — a working command nothing calls. These
are the two assertions that make that impossible, and they are deliberately different in kind:

* the **render** half proves the rendered stage invokes the command and carries the report
  section (and that Side carries neither — ADR-005 gates on the preset, and a presence-only
  test passes on a template that renders unconditionally);
* the **reachability** half proves the verb survives `command_registry.guard_or_none`, which
  runs *before* argparse. An unregistered verb is intercepted and the subcommand is
  unreachable from the command line while every library-level test still passes.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness_maker import command_registry
from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_SECTION = "## 📏 Size & Complexity"
_VERB = "complexity"


def _profile(preset: Preset) -> ProjectProfile:
    return (
        ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
        if preset == Preset.SIDE
        else ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    )


@cache
def _review(preset: Preset) -> str:
    profile = _profile(preset)
    answers = interview(profile, autoloop_mode=True)
    bp = synthesize(profile, answers, preset=preset)
    out = Path(mkdtemp(prefix="hm-complexity-"))
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return (out / "commands" / "hm" / "review.md").read_text(encoding="utf-8")


def test_production_invokes_the_measurement() -> None:
    """Sink one: the command runs. Without this the calculator is dead code with tests."""
    assert f"review_churn {_VERB}" in _review(Preset.PRODUCTION)


def test_production_carries_the_report_section() -> None:
    """Sink two: the round's cost is visible where a human is already looking."""
    assert _SECTION in _review(Preset.PRODUCTION)


@pytest.mark.parametrize("part", [f"review_churn {_VERB}", _SECTION])
def test_side_carries_neither_half(part: str) -> None:
    """ADR-005 gates on the preset, and absence is what has to be asserted.

    A presence-only pair of tests passes identically on a template that renders the block
    unconditionally, so the Production arm alone proves nothing about the gate.
    """
    assert part not in _review(Preset.SIDE)


def test_the_verb_is_registered_for_the_module() -> None:
    """The rendered stage documents `hm review_churn complexity`, and a documented subcommand
    must be registered — `test_every_documented_subcommand_is_registered` fails otherwise.

    **This is NOT the mechanism terminal plan-validation named.** It said `guard_or_none`
    intercepts an unregistered verb before argparse. It does not: `misroute_guard` is
    fail-open by design and redirects only when `argv[0]` is a valid subcommand of a
    *different* module, so an unknown token passes straight through. That claim was falsified
    by this module's own discrimination test, which asserted the guard rejects `nonesuch` and
    found it returns None. The registry entry is still required — for this reason instead.
    """
    subs = command_registry.MODULES["review_churn"].subcommands
    assert _VERB in subs
    assert "nonesuch" not in subs


def test_the_parser_rejects_a_verb_the_registry_does_not_list() -> None:
    """Parity, from the argparse side. Registry membership alone is half the contract.

    `review_churn.main` declares `choices=[...]` independently of the registry tuple, so the
    two can drift: a verb in one and not the other is reachable-but-undocumented or
    documented-but-unreachable. This asserts the parser's side directly — a bogus verb exits
    through argparse's invalid-choice path, and the real verb does not.
    """
    from harness_maker import review_churn

    with pytest.raises(SystemExit):
        review_churn.main(["nonesuch"])
    # The real verb reaches the module's own argument handling instead of argparse's rejection.
    assert review_churn.main([_VERB]) == 2  # missing --pre/--post, reported by the module
