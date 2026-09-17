"""AC-008 (SPEC-outcome-measure) — plan/review/help pinned, wrapup bounded, allowance retired.

The oracle is the PRE-CHANGE pin Phase 0 copied into `work-docs/BASELINE-DELTA-outcome-measure.md`
(ADR-007) — taken before any template edit, so it cannot be derived from the new render. While
the PLAN is in flight, wrapup may grow by at most the declared `surface_allowance.commands.wrapup`
per arm; at close-out (Phase 5) the allowance block is gone, wrapup is re-pinned, and the
structural gates are green with zero in-flight headroom, so main is green after the land.

The pin is task-time: every rendered command carries `harness_maker_version:`, so a release bump
moves all of them by construction. This test skips — loudly — once the shipped version differs.
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
_DELTA = _REPO / "work-docs" / "BASELINE-DELTA-outcome-measure.md"
_PLAN = _REPO / "work-docs" / "PLAN-outcome-measure.md"
_PINNED_UNCHANGED = ("plan", "review", "help")
_ARMS = {"ask@flag_off", "ask@flag_on", "auto_safe@spec-driven", "auto_safe@task-driven"}
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


def _wrapup_allowance() -> int:
    block = _plan_frontmatter().get("surface_allowance")
    if not isinstance(block, dict):
        return 0
    commands = block.get("commands")
    if not isinstance(commands, dict):
        return 0
    return int(commands.get("wrapup", 0))


def _live_arms(tmp_path: Path) -> dict[str, dict[str, str]]:
    live: dict[str, dict[str, str]] = {}

    def take(name: str, rendered: dict[str, str]) -> None:
        live[name] = {
            k: hashlib.sha256(v.encode()).hexdigest()
            for k, v in rendered.items()
            if k in ("plan", "review", "help", "wrapup")
        }
        live[name]["wrapup_len"] = str(len(rendered["wrapup"]))

    for dev_mode in AXES:
        take(f"auto_safe@{dev_mode.value}", _render_atomic(dev_mode))
    for flag, name in ((True, "ask@flag_on"), (False, "ask@flag_off")):
        take(name, _render(feature_branch_workflow=flag, tmp=tmp_path / name))
    return live


def _skip_on_version_bump(pin: dict[str, object]) -> None:
    pinned_version = pin.get("harness_maker_version")
    if pinned_version != __version__:
        pytest.skip(
            f"pin taken at {pinned_version}, shipped {__version__}: every command moved by the "
            "version line alone — re-pin at the next task that touches these commands"
        )


def test_ac_008_plan_review_help_pinned_and_wrapup_within_allowance(tmp_path: Path) -> None:
    pin = _pin()
    _skip_on_version_bump(pin)
    arms = pin["arms"]
    wrapup_len = pin["wrapup_len"]
    assert isinstance(arms, dict)
    assert isinstance(wrapup_len, dict)
    live = _live_arms(tmp_path)
    assert set(live) == set(arms), "the arm set drifted"
    moved = {
        arm: sorted(c for c in _PINNED_UNCHANGED if live[arm][c] != arms[arm][c])
        for arm in sorted(arms)
    }
    assert all(not m for m in moved.values()), f"pinned commands moved: {moved}"
    allowance = _wrapup_allowance()
    growth = {arm: int(live[arm]["wrapup_len"]) - int(wrapup_len[arm]) for arm in sorted(arms)}
    over = {arm: g for arm, g in growth.items() if g > allowance}
    assert not over, f"wrapup grew past the declared allowance ({allowance}): {over}"
    if allowance == 0:
        # Retired: wrapup was re-pinned at Phase 5 and is byte-identical from here on.
        drifted = {arm for arm in arms if live[arm]["wrapup"] != arms[arm]["wrapup"]}
        assert not drifted, f"wrapup moved after retirement: {sorted(drifted)}"


def test_ac_008_the_pin_names_every_arm_and_command_it_claims_to_cover() -> None:
    """Positive control — a pin missing an arm would make the test above vacuous for it."""
    pin = _pin()
    arms = pin["arms"]
    wrapup_len = pin["wrapup_len"]
    assert isinstance(arms, dict)
    assert isinstance(wrapup_len, dict)
    assert set(arms) == _ARMS == set(wrapup_len)
    for arm, shas in arms.items():
        assert set(shas) == {"plan", "review", "help", "wrapup"}, arm
        assert all(re.fullmatch(r"[0-9a-f]{64}", s) for s in shas.values()), arm
        assert int(wrapup_len[arm]) > 0


def test_ac_008_allowance_retired_and_structural_suite_green() -> None:
    """Close-out (ADR-007): no in-flight headroom is left behind for the next task to inherit.

    The suite-green half is the structural suite itself running in the same session; this test
    pins the two facts that make that run meaningful — the PLAN declares no allowance, and the
    aggregate the delta document quotes is the one the committed baseline actually holds.
    """
    fm = _plan_frontmatter()
    assert "surface_allowance" not in fm, "the allowance block was not retired (ADR-007 Phase 5)"
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
