"""AC-006 (SPEC-intent-layer-ops) — plan/review/help pinned, wrapup bounded, allowance retired.

The oracle is the PRE-CHANGE pin Phase 0 copied into `work-docs/BASELINE-DELTA-intent-layer-ops.md`
(ADR-005) — taken before any template edit, so it cannot be derived from the new render. While the
PLAN is in flight, wrapup may grow by at most the declared `surface_allowance.commands.wrapup` per
arm; at close-out (Phase 4) the allowance block is gone, wrapup is re-pinned, and the structural
gates are green with zero in-flight headroom, so main is green after the land.

The pin is task-time: every rendered command carries `harness_maker_version:`, so a release bump
moves all of them by construction. The render test skips — loudly — once the shipped version
differs. The recipe is reused from `test_outcome_measure_invariance` rather than copied.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from tests.structural.test_outcome_measure_invariance import (
    _ARMS,
    _PINNED_UNCHANGED,
    _live_arms,
    _skip_on_version_bump,
)

_REPO = Path(__file__).resolve().parents[2]
_DELTA = _REPO / "work-docs" / "BASELINE-DELTA-intent-layer-ops.md"
_PLAN = _REPO / "work-docs" / "PLAN-intent-layer-ops.md"
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


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


def _wrapup_allowance() -> int:
    block = _plan_frontmatter().get("surface_allowance")
    if not isinstance(block, dict):
        return 0
    commands = block.get("commands")
    return int(commands.get("wrapup", 0)) if isinstance(commands, dict) else 0


def test_ac_006_surface_pinned_and_allowance_retired(tmp_path: Path) -> None:
    pin = _pin()
    _skip_on_version_bump(pin)
    arms = pin["arms"]
    wrapup_len = pin["wrapup_len"]
    assert isinstance(arms, dict)
    assert isinstance(wrapup_len, dict)
    live = _live_arms(tmp_path)
    assert set(live) == set(arms) == _ARMS, "the arm set drifted"
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
        drifted = {arm for arm in arms if live[arm]["wrapup"] != arms[arm]["wrapup"]}
        assert not drifted, f"wrapup moved after retirement: {sorted(drifted)}"


def test_ac_006_allowance_retired_and_delta_doc_quotes_the_baseline() -> None:
    """Close-out: no in-flight headroom left behind, and the doc quotes the committed aggregate."""
    assert "surface_allowance" not in _plan_frontmatter(), "allowance block not retired (Phase 4)"
    from tests.structural.test_baseline_delta_attribution import _current_delta_doc

    current = _current_delta_doc()
    if current is not None and current.name != _DELTA.name:
        pytest.skip(
            f"a later task ({current.name}) moved the baseline; this document is historical"
        )
    baseline = json.loads(
        (_REPO / "tests" / "structural" / "surface_baseline.json").read_text(encoding="utf-8")
    )
    doc = _DELTA.read_text(encoding="utf-8")
    for variant, value in baseline["aggregate_chars"].items():
        grouped = f"{value:,}".replace(",", " ")
        assert grouped in doc or str(value) in doc, f"delta doc does not quote {variant}={value}"
