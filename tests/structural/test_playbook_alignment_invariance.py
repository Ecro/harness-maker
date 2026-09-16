"""AC-005 (SPEC-playbook-alignment) — plan / review / help and the boundary baseline are unchanged.

The oracle is the PRE-CHANGE pin Phase 0 copied into
`work-docs/BASELINE-DELTA-playbook-alignment.md`
(ADR-010) — not `autopilot_gate_golden.json`, which Phase 4 re-captures. A test that read the
re-captured golden could not tell "wrapup alone moved" from "wrapup plus three others moved".

The pin is task-time: every rendered command carries `harness_maker_version:`, so a release bump
moves all of them by construction. The pin records the version it was taken at and this test
skips — loudly — once the shipped version differs, instead of failing at the next release.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from harness_maker import __version__
from tests.structural._instruction_baseline import AXES, _render_atomic
from tests.structural.test_command_size_budget import _render

_REPO = Path(__file__).resolve().parents[2]
_DELTA = _REPO / "work-docs" / "BASELINE-DELTA-playbook-alignment.md"
_BOUNDARY = _REPO / "tests" / "fixtures" / "autopilot_caps_baseline.json"
_PINNED = ("plan", "review", "help")


def _pin() -> dict[str, object]:
    text = _DELTA.read_text(encoding="utf-8")
    m = re.search(r"```json\n(.*?)\n```", text, re.S)
    assert m, "the delta doc has no fenced JSON pin"
    return json.loads(m.group(1))  # type: ignore[no-any-return]


def _live_arms(tmp_path: Path) -> dict[str, dict[str, str]]:
    live: dict[str, dict[str, str]] = {}
    for dev_mode in AXES:
        rendered = _render_atomic(dev_mode)
        live[f"auto_safe@{dev_mode.value}"] = {
            k: hashlib.sha256(v.encode()).hexdigest() for k, v in rendered.items() if k in _PINNED
        }
    for flag, name in ((True, "ask@flag_on"), (False, "ask@flag_off")):
        rendered = _render(feature_branch_workflow=flag, tmp=tmp_path / name)
        live[name] = {
            k: hashlib.sha256(v.encode()).hexdigest() for k, v in rendered.items() if k in _PINNED
        }
    return live


def test_ac_005_plan_review_help_bytes_and_boundary_baseline_unchanged(tmp_path: Path) -> None:
    pin = _pin()
    pinned_version = pin.get("harness_maker_version")
    if pinned_version != __version__:
        pytest.skip(
            f"pin taken at {pinned_version}, shipped {__version__}: every command moved by the "
            "version line alone — re-pin at the next task that touches these commands"
        )
    arms = pin["arms"]
    assert isinstance(arms, dict)
    live = _live_arms(tmp_path)
    assert set(live) == set(arms), "the arm set drifted"
    moved = {
        arm: sorted(c for c in _PINNED if live[arm].get(c) != arms[arm][c]) for arm in sorted(arms)
    }
    assert all(not m for m in moved.values()), f"pinned commands moved: {moved}"
    boundary_sha = hashlib.sha256(_BOUNDARY.read_bytes()).hexdigest()
    assert boundary_sha == pin["boundary_baseline_sha256"], "the 77-cell boundary fixture moved"


def test_ac_005_the_pin_names_every_arm_and_command_it_claims_to_cover() -> None:
    """Positive control — a pin missing an arm would make the test above vacuous for it."""
    pin = _pin()
    arms = pin["arms"]
    assert isinstance(arms, dict)
    expected = {"ask@flag_off", "ask@flag_on", "auto_safe@spec-driven", "auto_safe@task-driven"}
    assert set(arms) == expected
    for arm, shas in arms.items():
        assert set(shas) == set(_PINNED), arm
        assert all(re.fullmatch(r"[0-9a-f]{64}", s) for s in shas.values()), arm
    assert re.fullmatch(r"[0-9a-f]{64}", str(pin["boundary_baseline_sha256"]))
