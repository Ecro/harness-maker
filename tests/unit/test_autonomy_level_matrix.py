"""Phase B1 — one constant, one normalization owner, and the cases that were never asserted.

Two of these pin behaviour that the pre-B1 code got wrong in a way no test would have caught:

* `arm_if_persistent` reached its arming level through a hand-written if/elif ladder ending in
  `else: return False`. Adding `auto_full` to the config without touching the ladder would have
  made the flagship level **silently never arm** — no error, no log, autopilot just off.
* `_parse_autonomy` discarded the ENTIRE block on an unrecognised level, taking the user's
  caps, pipeline and `extra_deny` with it. `extra_deny` is an additive security baseline, so a
  one-word typo silently subtracted a guard.

The `ask` cases are the absent-case guard for this PLAN's own new value: `ask` must reach the
picker, and every runtime surface must refuse it rather than write a marker nothing can act on.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from harness_maker import autopilot, autopilot_ledger
from harness_maker.hooks.autopilot_autoarm import arm_if_persistent
from harness_maker.interview import _parse_autonomy
from harness_maker.models import ARMED_LEVELS, OPERATIONAL_LEVELS, AutonomyConfig

_SESSION = "b1-matrix-session"


def _write_yaml(root: Path, *, level: str, persistent: bool) -> None:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "harness.yaml").write_text(
        f"autonomy:\n  level: {level}\n  autopilot_persistent: {str(persistent).lower()}\n",
        encoding="utf-8",
    )


# ── 1 + 9: the legacy spelling normalizes, at both layers ─────────────────────


def test_legacy_full_demotes_to_auto_safe() -> None:
    assert AutonomyConfig(level="full").level == "auto_safe"


def test_a_marker_written_by_an_older_version_still_loads(tmp_path: Path) -> None:
    """The silent-degradation case: a strict reject here reads as 'autopilot is off'."""
    autopilot.write(
        tmp_path,
        level="auto_safe",
        pipeline=list(AutonomyConfig().pipeline),
        claude_session_id=_SESSION,
    )
    path = autopilot.marker_path(tmp_path, session_id=_SESSION)
    path.write_text(path.read_text().replace('"auto_safe"', '"full"'), encoding="utf-8")
    marker = autopilot.load(tmp_path, session_id=_SESSION)
    assert marker is not None, "a legacy `full` marker was dropped instead of normalized"
    assert marker.level == "auto_safe"


# ── 2: an unknown level demotes the LEVEL, not the block ──────────────────────


def test_unknown_level_keeps_its_siblings() -> None:
    cfg = _parse_autonomy({"level": "typo", "step_cap": 7, "time_cap_min": 9})
    assert cfg.level == "gated"
    assert cfg.step_cap == 7
    assert cfg.time_cap_min == 9


def test_unknown_level_does_not_subtract_extra_deny() -> None:
    cfg = _parse_autonomy({"level": "typo", "extra_deny": ["Bash(curl:*)"]})
    assert cfg.extra_deny == ["Bash(curl:*)"]


# ── 3: `ask` is yaml-only ─────────────────────────────────────────────────────


def test_ask_is_accepted_by_the_config() -> None:
    assert AutonomyConfig(level="ask").level == "ask"


def test_ask_is_refused_by_every_runtime_surface() -> None:
    assert "ask" not in autopilot._VALID_LEVELS
    with pytest.raises(ValueError, match="invalid --level") as exc:
        autopilot.resolve_toggle_config("ask", None)
    for operational in OPERATIONAL_LEVELS:
        assert operational in str(exc.value), f"the error must name {operational}"


def test_the_ledger_cli_refuses_ask() -> None:
    with pytest.raises(SystemExit):
        autopilot_ledger.main(["smoke", "--level", "ask"])


# ── 4 + 5: arming ─────────────────────────────────────────────────────────────


def test_auto_full_arms(tmp_path: Path) -> None:
    _write_yaml(tmp_path, level="auto_full", persistent=True)
    assert arm_if_persistent(tmp_path, claude_session_id=_SESSION) is True
    marker = autopilot.load(tmp_path, session_id=_SESSION)
    assert marker is not None
    assert marker.level == "auto_full"


def test_ask_plus_persistent_writes_no_marker_and_logs_no_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The picker owns the session (ADR-003). A silent no-op is correct here, not a failure."""
    _write_yaml(tmp_path, level="ask", persistent=True)
    with caplog.at_level(logging.WARNING):
        assert arm_if_persistent(tmp_path, claude_session_id=_SESSION) is False
    assert autopilot.load(tmp_path, session_id=_SESSION) is None
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING], caplog.records


def test_gated_still_does_not_arm(tmp_path: Path) -> None:
    _write_yaml(tmp_path, level="gated", persistent=True)
    assert arm_if_persistent(tmp_path, claude_session_id=_SESSION) is False


def test_legacy_full_still_arms(tmp_path: Path) -> None:
    """A committed `full` must keep behaving exactly as it did — as `auto_safe`."""
    _write_yaml(tmp_path, level="full", persistent=True)
    assert arm_if_persistent(tmp_path, claude_session_id=_SESSION) is True
    marker = autopilot.load(tmp_path, session_id=_SESSION)
    assert marker is not None
    assert marker.level == "auto_safe"


# ── 6: derivation, not restatement ────────────────────────────────────────────


def test_armed_levels_are_derived() -> None:
    assert set(OPERATIONAL_LEVELS) - {"gated"} == ARMED_LEVELS
    assert autopilot_ledger._ARMED_LEVELS == ARMED_LEVELS


# ── 8: the `--update` advisory ────────────────────────────────────────────────


def test_advisory_fires_for_legacy_full(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        _parse_autonomy({"level": "full", "autopilot_persistent": True})
    assert any("pre-0.51" in r.message for r in caplog.records), caplog.records


def test_advisory_does_not_fire_for_a_current_level(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        _parse_autonomy({"level": "auto_safe", "autopilot_persistent": True})
    assert not [r for r in caplog.records if "pre-0.51" in r.message], caplog.records
