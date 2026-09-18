"""AC-012 (SPEC-assumption-entry-and-evidence-locator) — plan/review/help pinned, wrapup bounded.

The oracle is the PRE-CHANGE pin Phase 0 wrote into
`work-docs/BASELINE-DELTA-assumption-entry-and-evidence-locator.md` before any template edit, so
it cannot be derived from the new render. While the PLAN declares `surface_allowance`, wrapup may
grow by at most `commands.wrapup` per arm; with no allowance, wrapup must be byte-identical to the
pin (Phase 5 re-pins it at retirement). The pin is task-time — it skips loudly on a version bump.

This test passes before the Phase 4 template edit by design: it is the negative invariant ("the
growth is declared and bounded"). Its positive sibling, `test_ac_010_wrapup_offers_add_and_lists_
stale_first`, is RED until the template changes, and the moment the template changes without an
allowance this one goes red.
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
_DELTA = _REPO / "work-docs" / "BASELINE-DELTA-assumption-entry-and-evidence-locator.md"
_PLAN = _REPO / "work-docs" / "PLAN-assumption-entry-and-evidence-locator.md"
_PINNED_UNCHANGED = ("plan", "review", "help")
_ARMS = {"ask@flag_off", "ask@flag_on", "auto_safe@spec-driven", "auto_safe@task-driven"}
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def _pin() -> dict[str, object]:
    m = re.search(r"```json\n(.*?)\n```", _DELTA.read_text(encoding="utf-8"), re.S)
    assert m, "the delta doc has no fenced JSON pin"
    return json.loads(m.group(1))  # type: ignore[no-any-return]


def _wrapup_allowance() -> int:
    if not _PLAN.exists():
        return 0
    m = _FRONTMATTER.match(_PLAN.read_text(encoding="utf-8"))
    block = (yaml.safe_load(m.group(1)) or {}).get("surface_allowance") if m else None
    if not isinstance(block, dict) or not isinstance(block.get("commands"), dict):
        return 0
    return int(block["commands"].get("wrapup", 0))


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


def test_ac_012_surface_pinned_and_allowance_retired(tmp_path: Path) -> None:
    pin = _pin()
    if pin.get("harness_maker_version") != __version__:
        pytest.skip(
            f"pin taken at {pin.get('harness_maker_version')}, shipped {__version__}: every "
            "command moved by the version line alone — re-pin at the next task that touches them"
        )
    from tests.structural.test_baseline_delta_attribution import _current_delta_doc

    current = _current_delta_doc()
    if current is not None and current.name != _DELTA.name:
        # A later task moved the surface inside the same release; its invariance test owns the pin.
        pytest.skip(f"a later task ({current.name}) moved the surface; its test owns the pin")
    arms = pin["arms"]
    wrapup_len = pin["wrapup_len"]
    assert isinstance(arms, dict)
    assert isinstance(wrapup_len, dict)
    live = _live_arms(tmp_path)
    assert set(live) == set(arms), "the arm set drifted"
    moved = {a: [c for c in _PINNED_UNCHANGED if live[a][c] != arms[a][c]] for a in sorted(arms)}
    assert all(not m for m in moved.values()), f"pinned commands moved: {moved}"
    allowance = _wrapup_allowance()
    if allowance:
        growth = {a: int(live[a]["wrapup_len"]) - int(wrapup_len[a]) for a in sorted(arms)}
        over = {a: g for a, g in growth.items() if g > allowance}
        assert not over, f"wrapup grew past the declared allowance ({allowance}): {over}"
    else:
        drifted = sorted(a for a in arms if live[a]["wrapup"] != arms[a]["wrapup"])
        assert not drifted, f"wrapup moved with no declared allowance: {drifted}"


def test_ac_012_the_pin_names_every_arm_and_command_it_claims_to_cover() -> None:
    """Positive control — a pin missing an arm would make the test above vacuous for it."""
    pin = _pin()
    arms, wrapup_len = pin["arms"], pin["wrapup_len"]
    assert isinstance(arms, dict)
    assert isinstance(wrapup_len, dict)
    assert set(arms) == _ARMS == set(wrapup_len)
    for arm, shas in arms.items():
        assert set(shas) == {"plan", "review", "help", "wrapup"}, arm
        assert all(re.fullmatch(r"[0-9a-f]{64}", s) for s in shas.values()), arm
        assert int(wrapup_len[arm]) > 0
