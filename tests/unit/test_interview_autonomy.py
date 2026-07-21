"""PLAN-autopilot-config-surface P4 — `_ask_autonomy` interview round + reverse-map preservation.

ADR-001 surfaces ONLY autonomy/autopilot in the interview. ADR-002: unlimited is the offered
default for a fresh harness; a numeric entry sets a finite (>0) cap. Preservation across
re-render is owned by `_parse_autonomy` (the reverse-mapper), which must round-trip null caps,
finite caps, and the persistent flag unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_maker import interview as iv
from harness_maker.interview import _ask_autonomy, answers_from_harness_yaml
from harness_maker.io_utils import atomic_write


def _feed(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    it: Iterator[str] = iter(answers)

    def _fake(_prompt: str) -> str:
        return next(it, "")

    monkeypatch.setattr(iv, "_input_or_empty", _fake)


def test_ask_autonomy_disabled_returns_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed(monkeypatch, ["n"])
    cfg = _ask_autonomy()
    assert cfg.level == "gated"
    assert cfg.autopilot_persistent is False


def test_ask_autonomy_enabled_defaults_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    # enable=y, level=default(auto_safe), persistent=default(n), step+time=default(unlimited)
    _feed(monkeypatch, ["y", "", "", "", ""])
    cfg = _ask_autonomy()
    assert cfg.level == "auto_safe"
    assert cfg.autopilot_persistent is False
    assert cfg.step_cap is None
    assert cfg.time_cap_min is None


def test_ask_autonomy_persistent_and_finite_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    # enable, level=full, persist=y, step=5, time=60.
    _feed(monkeypatch, ["y", "full", "y", "5", "60"])
    cfg = _ask_autonomy()
    assert cfg.level == "full"
    assert cfg.autopilot_persistent is True
    assert cfg.step_cap == 5
    assert cfg.time_cap_min == 60


def test_ask_autonomy_non_persistent(monkeypatch: pytest.MonkeyPatch) -> None:
    # Not persistent → enable, level(default), persist=n, step, time.
    _feed(monkeypatch, ["y", "", "", "7", "70"])
    cfg = _ask_autonomy()
    assert cfg.autopilot_persistent is False
    assert cfg.step_cap == 7


def test_ask_autonomy_invalid_cap_falls_back_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    # A non-positive / non-numeric cap entry is not a valid bound → unlimited (None), never 0.
    _feed(monkeypatch, ["y", "", "", "0", "abc"])
    cfg = _ask_autonomy()
    assert cfg.step_cap is None
    assert cfg.time_cap_min is None


# ── reverse-map preservation (the validator's re-render concern) ─────────────


def _write(root: Path, body: str) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    p = root / ".claude" / "harness.yaml"
    atomic_write(p, body)
    return p


def test_parse_autonomy_preserves_null_caps_and_persistent(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "preset: Production\nlocale: en\ntargets: [claude-code]\n"
        "autonomy:\n  level: auto_safe\n  step_cap: null\n  time_cap_min: null\n"
        "  autopilot_persistent: true\n",
    )
    answers = answers_from_harness_yaml(p)
    assert answers is not None
    assert answers.autonomy.step_cap is None
    assert answers.autonomy.time_cap_min is None
    assert answers.autonomy.autopilot_persistent is True


def test_parse_autonomy_preserves_finite_caps(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "preset: Production\nlocale: en\ntargets: [claude-code]\n"
        "autonomy:\n  level: full\n  step_cap: 12\n  time_cap_min: 90\n",
    )
    answers = answers_from_harness_yaml(p)
    assert answers is not None
    assert answers.autonomy.step_cap == 12
    assert answers.autonomy.time_cap_min == 90
    assert answers.autonomy.autopilot_persistent is False


def test_parse_autonomy_drops_retired_guard_when(tmp_path: Path) -> None:
    # guard_when was RETIRED; an old harness.yaml still carrying it must NOT reset the whole
    # autonomy block to defaults (AutonomyConfig forbids extras) — the key is dropped and the
    # rest of the config is preserved (retired-key migration).
    p = _write(
        tmp_path,
        "preset: Production\nlocale: en\ntargets: [claude-code]\n"
        "autonomy:\n  level: full\n  step_cap: 9\n  autopilot_persistent: true\n"
        "  guard_when: pipeline_only\n",
    )
    answers = answers_from_harness_yaml(p)
    assert answers is not None
    assert answers.autonomy.level == "full"
    assert answers.autonomy.step_cap == 9
    assert answers.autonomy.autopilot_persistent is True
    assert not hasattr(answers.autonomy, "guard_when")
