"""SPEC-ai-native-sdlc-vs-intent-world ADR-007 — plan/review pinned, four commands bounded.

The oracle is the PRE-CHANGE pin Phase 0 copied into
`work-docs/BASELINE-DELTA-ai-native-sdlc-vs-intent-world.md`, taken before any source edit, so it
cannot be derived from the new render. While the PLAN is in flight, `spec`, `execute`, `wrapup`
and `loop` may grow by at most the declared `surface_allowance.commands.<name>` per arm; at
close-out (Phase 5) the allowance block is gone, the four are re-pinned, and every pinned command
is byte-identical to the pin. Hand-over to a later task follows
`test_mission_context_loop_invariance`.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

import pytest
import yaml

from tests.structural._instruction_baseline import AXES, _render_atomic
from tests.structural.test_command_size_budget import _render
from tests.structural.test_outcome_measure_invariance import _ARMS, _skip_on_version_bump

_REPO = Path(__file__).resolve().parents[2]
_DELTA = _REPO / "work-docs" / "BASELINE-DELTA-ai-native-sdlc-vs-intent-world.md"
_PLAN = _REPO / "work-docs" / "PLAN-ai-native-sdlc-vs-intent-world.md"
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_PINNED_UNCHANGED = ("plan", "review")
_BOUNDED = ("spec", "execute", "wrapup", "loop")


def _pin() -> dict[str, object]:
    m = re.search(r"```json\n(.*?)\n```", _DELTA.read_text(encoding="utf-8"), re.S)
    assert m, "the delta doc has no fenced JSON pin"
    return json.loads(m.group(1))  # type: ignore[no-any-return]


def _plan_frontmatter() -> dict[str, object]:
    m = _FRONTMATTER.match(_PLAN.read_text(encoding="utf-8"))
    assert m, "PLAN has no frontmatter"
    loaded = yaml.safe_load(m.group(1))
    assert isinstance(loaded, dict)
    return loaded


def _allowance(command: str) -> int:
    block = _plan_frontmatter().get("surface_allowance")
    if not isinstance(block, dict):
        return 0
    commands = block.get("commands")
    return int(commands.get(command, 0)) if isinstance(commands, dict) else 0


def _live() -> dict[str, dict[str, str]]:
    live: dict[str, dict[str, str]] = {}

    def take(name: str, rendered: dict[str, str]) -> None:
        live[name] = {
            k: hashlib.sha256(rendered[k].encode()).hexdigest()
            for k in (*_PINNED_UNCHANGED, *_BOUNDED)
        }
        for k in _BOUNDED:
            live[name][f"{k}_len"] = str(len(rendered[k]))

    for strictness in AXES:
        take(f"auto_safe@{strictness}", _render_atomic(strictness))
    tmp = Path(tempfile.mkdtemp())
    for flag, name in ((True, "ask@flag_on"), (False, "ask@flag_off")):
        take(name, _render(feature_branch_workflow=flag, tmp=tmp / name))
    return live


def _skip_when_a_later_task_owns_the_surface() -> None:
    """Hand over only AFTER retirement (same rule as the mission-context-loop test)."""
    if "surface_allowance" in _plan_frontmatter():
        return
    from tests.structural.test_baseline_delta_attribution import _current_delta_doc

    current = _current_delta_doc()
    if current is not None and current.name != _DELTA.name:
        pytest.skip(
            f"a later task ({current.name}) moved the surface; its own invariance test owns the pin"
        )


def test_plan_review_pinned_and_four_commands_within_allowance() -> None:
    pin = _pin()
    _skip_on_version_bump(pin)
    _skip_when_a_later_task_owns_the_surface()
    arms = pin["arms"]
    lengths = pin["len"]
    assert isinstance(arms, dict)
    assert isinstance(lengths, dict)
    live = _live()
    assert set(live) == set(arms) == _ARMS, "the arm set drifted"
    moved = {
        arm: sorted(c for c in _PINNED_UNCHANGED if live[arm][c] != arms[arm][c])
        for arm in sorted(arms)
    }
    assert all(not m for m in moved.values()), f"pinned commands moved: {moved}"
    for command in _BOUNDED:
        allowance = _allowance(command)
        growth = {
            arm: int(live[arm][f"{command}_len"]) - int(lengths[arm][command]) for arm in arms
        }
        over = {arm: g for arm, g in growth.items() if g > allowance}
        assert not over, f"{command} grew past its allowance ({allowance}): {over}"
        if allowance == 0:
            drifted = sorted(arm for arm in arms if live[arm][command] != arms[arm][command])
            assert not drifted, f"{command} moved without an allowance: {drifted}"


def test_allowance_retired_and_delta_doc_quotes_the_baseline() -> None:
    """Close-out: no in-flight headroom left behind, and the doc quotes the committed aggregate."""
    if _plan_frontmatter().get("status") == "planning":
        pytest.skip("PLAN in flight — retirement is Phase 5's exit")
    assert "surface_allowance" not in _plan_frontmatter(), "allowance block not retired (Phase 5)"
    _skip_when_a_later_task_owns_the_surface()
    baseline = json.loads(
        (_REPO / "tests" / "structural" / "surface_baseline.json").read_text(encoding="utf-8")
    )
    doc = _DELTA.read_text(encoding="utf-8")
    for variant, value in baseline["aggregate_chars"].items():
        grouped = f"{value:,}".replace(",", " ")
        assert grouped in doc or str(value) in doc, f"delta doc does not quote {variant}={value}"
