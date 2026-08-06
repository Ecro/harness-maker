"""Phase 6 (ADR-008): new-harness default for the feature-branch model.

A freshly-rendered PRODUCTION harness defaults
`worktree.enabled = True` (set in `_preset_extras`); a SIDE harness
does not — the flag is inert without worktree isolation and would mis-render the
Phase-5 preflight. End-to-end coverage lives in the snapshot fixtures (the 4
Production fixtures now render the flag-on preflight); this pins the source default.
"""

from __future__ import annotations

from harness_maker.interview import _preset_extras
from harness_maker.models import Preset


def test_production_new_default_flag_on() -> None:
    extras = _preset_extras(Preset.PRODUCTION)
    assert extras["worktree"] == {"enabled": True}
    assert extras["worktree"]["enabled"] is True


def test_side_new_default_flag_absent() -> None:
    extras = _preset_extras(Preset.SIDE)
    assert extras["worktree"] == {"enabled": False}
    assert extras["worktree"]["enabled"] is False
