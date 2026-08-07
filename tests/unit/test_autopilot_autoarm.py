"""PLAN-autopilot-config-surface P3 — SessionStart auto-arm hook (ADR-003).

When ``autonomy.autopilot_persistent: true`` is committed, a SessionStart hook re-arms a
fresh ``.hm-autopilot`` marker each session from the committed level/pipeline, so the 18h
TTL never trips in practice. The re-arm TRUTH TABLE is the oracle: persistent-false → no
arm; gated → no-op; auto_safe/full → arm; malformed/missing yaml → fail-safe no-op; a write
failure never raises (never blocks SessionStart).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import autopilot
from harness_maker.hooks import autopilot_autoarm
from harness_maker.io_utils import atomic_write

_FROZEN = "2026-06-25T12:00:00+00:00"


def _write_harness(root: Path, autonomy_block: str) -> None:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    atomic_write(root / ".claude" / "harness.yaml", autonomy_block)


_AUTO_SAFE = (
    "preset: Production\n"
    "autonomy:\n"
    "  level: auto_safe\n"
    "  pipeline: [research, spec, plan, execute, review, verify, wrapup]\n"
    "  step_cap: null\n"
    "  time_cap_min: null\n"
    "  autopilot_persistent: true\n"
)


def test_arms_when_persistent_and_auto_safe(tmp_path: Path) -> None:
    _write_harness(tmp_path, _AUTO_SAFE)
    armed = autopilot_autoarm.arm_if_persistent(tmp_path, now=_FROZEN)
    assert armed is True
    # load() (not active_marker) — the frozen created_at is intentionally outside the live
    # freshness window; the truth-table assertion is only that a marker with the right level
    # was WRITTEN. Freshness/TTL behavior is covered by autopilot.py's own tests.
    marker = autopilot.load(tmp_path, session_id=None)
    assert marker is not None
    assert marker.level == "auto_safe"


def test_arms_when_persistent_and_full(tmp_path: Path) -> None:
    _write_harness(tmp_path, _AUTO_SAFE.replace("auto_safe", "full"))
    assert autopilot_autoarm.arm_if_persistent(tmp_path, now=_FROZEN) is True
    marker = autopilot.load(tmp_path, session_id=None)
    assert marker is not None
    assert marker.level == "full"


def test_no_arm_when_persistent_false(tmp_path: Path) -> None:
    _write_harness(
        tmp_path, _AUTO_SAFE.replace("autopilot_persistent: true", "autopilot_persistent: false")
    )
    assert autopilot_autoarm.arm_if_persistent(tmp_path, now=_FROZEN) is False
    assert autopilot.load(tmp_path, session_id=None) is None


def test_no_arm_when_gated(tmp_path: Path) -> None:
    # persistent true but gated → no-op (gated never auto-advances).
    _write_harness(tmp_path, _AUTO_SAFE.replace("level: auto_safe", "level: gated"))
    assert autopilot_autoarm.arm_if_persistent(tmp_path, now=_FROZEN) is False
    assert autopilot.load(tmp_path, session_id=None) is None


def test_missing_harness_yaml_no_raise(tmp_path: Path) -> None:
    assert autopilot_autoarm.arm_if_persistent(tmp_path, now=_FROZEN) is False


def test_malformed_yaml_no_raise(tmp_path: Path) -> None:
    _write_harness(tmp_path, "preset: Production\nautonomy: [not, a, mapping]\n")
    assert autopilot_autoarm.arm_if_persistent(tmp_path, now=_FROZEN) is False


def test_invalid_pipeline_stage_is_fail_safe(tmp_path: Path) -> None:
    _write_harness(
        tmp_path,
        _AUTO_SAFE.replace(
            "pipeline: [research, spec, plan, execute, review, verify, wrapup]",
            "pipeline: [bogus_stage]",
        ),
    )
    assert autopilot_autoarm.arm_if_persistent(tmp_path, now=_FROZEN) is False
    assert autopilot.load(tmp_path, session_id=None) is None


def test_write_failure_is_fail_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_harness(tmp_path, _AUTO_SAFE)

    def _boom(*_a: object, **_k: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(autopilot_autoarm.autopilot, "write", _boom)
    # Must NOT raise — a hook that blocks SessionStart is worse than a degraded fallback.
    assert autopilot_autoarm.arm_if_persistent(tmp_path, now=_FROZEN) is False


def test_rearm_refreshes_created_at(tmp_path: Path) -> None:
    _write_harness(tmp_path, _AUTO_SAFE)
    autopilot_autoarm.arm_if_persistent(tmp_path, now="2026-06-25T08:00:00+00:00")
    first = autopilot.load(tmp_path, session_id=None)
    autopilot_autoarm.arm_if_persistent(tmp_path, now="2026-06-25T20:00:00+00:00")
    second = autopilot.load(tmp_path, session_id=None)
    assert first is not None
    assert second is not None
    assert second.created_at != first.created_at
    assert second.created_at == "2026-06-25T20:00:00+00:00"


def test_run_entry_uses_cwd_no_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_harness(tmp_path, _AUTO_SAFE)
    monkeypatch.chdir(tmp_path)
    # main() must always exit 0 (fail-safe), regardless of arm outcome.
    assert autopilot_autoarm.main() == 0
