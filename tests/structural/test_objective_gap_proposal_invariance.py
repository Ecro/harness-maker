"""AC-007 / AC-008 (SPEC-objective-gap-proposal) — review/help pinned, plan bounded, retired.

The oracle is the PRE-CHANGE pin Phase 0 copied into
`work-docs/BASELINE-DELTA-objective-gap-proposal.md` (ADR-007) — taken before any template
edit, so it cannot be derived from the new render. AC-007 holds while the PLAN is in flight
(plan may grow by at most the declared `surface_allowance.commands.plan` per arm); AC-008 is
the close-out (ADR-008): the allowance block is gone and the structural gates are green with
zero in-flight headroom, so main is green after the land.

The pin is task-time: every rendered command carries `harness_maker_version:`, so a release
bump moves all of them by construction. This test skips — loudly — once the shipped version
differs from the pinned one.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from harness_maker import __version__
from tests.structural._instruction_baseline import AXES, _render_atomic
from tests.structural.test_command_size_budget import _render

_REPO = Path(__file__).resolve().parents[2]
_DELTA = _REPO / "work-docs" / "BASELINE-DELTA-objective-gap-proposal.md"
_PLAN = _REPO / "work-docs" / "PLAN-objective-gap-proposal.md"
_PINNED_UNCHANGED = ("review", "help")
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def _pin() -> dict[str, object]:
    text = _DELTA.read_text(encoding="utf-8")
    m = re.search(r"```json\n(.*?)\n```", text, re.S)
    assert m, "the delta doc has no fenced JSON pin"
    return json.loads(m.group(1))  # type: ignore[no-any-return]


def _plan_frontmatter() -> dict[str, object]:
    m = _FRONTMATTER.match(_PLAN.read_text(encoding="utf-8"))
    assert m, "PLAN has no frontmatter"
    loaded = yaml.safe_load(m.group(1))
    assert isinstance(loaded, dict)
    return loaded


def _plan_allowance() -> int:
    block = _plan_frontmatter().get("surface_allowance")
    if not isinstance(block, dict):
        return 0
    commands = block.get("commands")
    if not isinstance(commands, dict):
        return 0
    return int(commands.get("plan", 0))


def _live_arms(tmp_path: Path) -> dict[str, dict[str, str]]:
    live: dict[str, dict[str, str]] = {}
    for strictness in AXES:
        rendered = _render_atomic(strictness)
        live[f"auto_safe@{strictness}"] = {
            k: hashlib.sha256(v.encode()).hexdigest()
            for k, v in rendered.items()
            if k in ("plan", "review", "help")
        }
        live[f"auto_safe@{strictness}"]["plan_len"] = str(len(rendered["plan"]))
    for flag, name in ((True, "ask@flag_on"), (False, "ask@flag_off")):
        rendered = _render(feature_branch_workflow=flag, tmp=tmp_path / name)
        live[name] = {
            k: hashlib.sha256(v.encode()).hexdigest()
            for k, v in rendered.items()
            if k in ("plan", "review", "help")
        }
        live[name]["plan_len"] = str(len(rendered["plan"]))
    return live


def _skip_on_version_bump(pin: dict[str, object]) -> None:
    pinned_version = pin.get("harness_maker_version")
    if pinned_version != __version__:
        pytest.skip(
            f"pin taken at {pinned_version}, shipped {__version__}: every command moved by the "
            "version line alone — re-pin at the next task that touches these commands"
        )


def test_ac_007_review_help_pinned_and_plan_within_allowance(tmp_path: Path) -> None:
    pin = _pin()
    _skip_on_version_bump(pin)
    arms = pin["arms"]
    plan_len = pin["plan_len"]
    assert isinstance(arms, dict)
    assert isinstance(plan_len, dict)
    live = _live_arms(tmp_path)
    assert set(live) == set(arms), "the arm set drifted"
    moved = {
        arm: sorted(c for c in _PINNED_UNCHANGED if live[arm][c] != arms[arm][c])
        for arm in sorted(arms)
    }
    assert all(not m for m in moved.values()), f"pinned commands moved: {moved}"
    allowance = _plan_allowance()
    growth = {arm: int(live[arm]["plan_len"]) - int(plan_len[arm]) for arm in sorted(arms)}
    over = {arm: g for arm, g in growth.items() if g > allowance}
    assert not over, f"plan grew past the declared allowance ({allowance}): {over}"


def test_ac_007_the_pin_names_every_arm_and_command_it_claims_to_cover() -> None:
    """Positive control — a pin missing an arm would make the test above vacuous for it."""
    pin = _pin()
    arms = pin["arms"]
    plan_len = pin["plan_len"]
    assert isinstance(arms, dict)
    assert isinstance(plan_len, dict)
    expected = {"ask@flag_off", "ask@flag_on", "auto_safe@block", "auto_safe@warn"}
    assert set(arms) == expected == set(plan_len)
    for arm, shas in arms.items():
        assert set(shas) == {"plan", "review", "help"}, arm
        assert all(re.fullmatch(r"[0-9a-f]{64}", s) for s in shas.values()), arm
        assert int(plan_len[arm]) > 0


def test_ac_008_allowance_retired_and_structural_suite_green() -> None:
    """Close-out (ADR-008): no in-flight headroom is left behind for the next task to inherit.

    The suite-green half is the structural suite itself running in the same session; this test
    pins the two facts that make that run meaningful — the PLAN declares no allowance, and the
    aggregate the delta document quotes is the one the committed baseline actually holds.
    """
    fm = _plan_frontmatter()
    assert "surface_allowance" not in fm, "the allowance block was not retired (ADR-008 Phase 6)"
    from tests.structural.test_baseline_delta_attribution import _current_delta_doc

    current = _current_delta_doc()
    if current is not None and current.name != _DELTA.name:
        pytest.skip(
            f"a later task ({current.name}) moved the baseline; this document is historical — "
            "the aggregate quote is checked against that task's document instead"
        )
    baseline = json.loads(
        (_REPO / "tests" / "structural" / "surface_baseline.json").read_text(encoding="utf-8")
    )
    doc = _DELTA.read_text(encoding="utf-8")
    for variant, value in baseline["aggregate_chars"].items():
        grouped = f"{value:,}".replace(",", " ")
        assert grouped in doc or str(value) in doc, f"delta doc does not quote {variant}={value}"
