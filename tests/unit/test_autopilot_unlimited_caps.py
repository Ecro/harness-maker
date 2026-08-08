"""PLAN-autopilot-config-surface P1/P2/P4 — nullable caps (None=unlimited) + autopilot_persistent.

ADR-002: ``step_cap``/``time_cap_min`` become ``int | None`` where ``None`` = unlimited
(the boundary cap check is skipped). The Pydantic field DEFAULT stays bounded (20/300) so
the absent/malformed fallback is safe (ADR-005) — only a fresh interview opts into unlimited.
The ``gt=0`` rule is preserved for non-None values (0/negative still rejected). ADR-003 adds
``autopilot_persistent``. These assertions are the P1 exit criterion + the serialize-to-
consumed-file invariant for the new fields.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker import autopilot, autopilot_caps
from harness_maker.models import (
    AutonomyConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_PIPELINE = list(AutonomyConfig().pipeline)


def _arm(root: Path, *, created: datetime, level: str = "auto_safe") -> None:
    autopilot.write(root, level=level, pipeline=_PIPELINE, now=created.isoformat())


# ── model: nullable caps + gt=0 preserved + persistent ──────────────────────


def test_autonomy_config_accepts_none_caps() -> None:
    cfg = AutonomyConfig(step_cap=None, time_cap_min=None)
    assert cfg.step_cap is None
    assert cfg.time_cap_min is None


def test_autonomy_config_field_default_stays_bounded() -> None:
    # ADR-002/005: absent/fallback default is bounded, NOT unlimited.
    cfg = AutonomyConfig()
    assert cfg.step_cap == 20
    assert cfg.time_cap_min == 300
    # ADR-010 promoted persistence; the CAPS are what this test guards, and they stay
    # bounded. Persistence divergence lives in tests/unit/test_autonomy_defaults.py.
    assert cfg.autopilot_persistent is True


@pytest.mark.parametrize("bad", [0, -1, -100])
def test_autonomy_config_rejects_zero_and_negative_step_cap(bad: int) -> None:
    with pytest.raises(ValidationError):
        AutonomyConfig(step_cap=bad)


@pytest.mark.parametrize("bad", [0, -1])
def test_autonomy_config_rejects_zero_and_negative_time_cap(bad: int) -> None:
    with pytest.raises(ValidationError):
        AutonomyConfig(time_cap_min=bad)


def test_autopilot_persistent_accepts_true() -> None:
    assert AutonomyConfig(autopilot_persistent=True).autopilot_persistent is True


# ── evaluate_boundary: None skips the cap, finite still halts ────────────────


def test_none_step_cap_never_step_halts(tmp_path: Path) -> None:
    _arm(tmp_path, created=datetime.now(UTC))
    decision = autopilot_caps.evaluate_boundary(
        tmp_path, steps=10_000, step_cap=None, time_cap_min=None
    )
    assert decision.proceed is True
    assert decision.halt_kind is None


def test_none_time_cap_never_time_halts(tmp_path: Path) -> None:
    # A marker created far in the past would trip a finite time cap; None must skip it.
    old = datetime.now(UTC) - timedelta(hours=5)
    _arm(tmp_path, created=old)
    decision = autopilot_caps.evaluate_boundary(tmp_path, steps=0, step_cap=None, time_cap_min=None)
    assert decision.proceed is True


def test_finite_step_cap_still_halts(tmp_path: Path) -> None:
    _arm(tmp_path, created=datetime.now(UTC))
    decision = autopilot_caps.evaluate_boundary(tmp_path, steps=2, step_cap=2, time_cap_min=None)
    assert decision.proceed is False
    assert decision.halt_kind == "step_cap"


def test_finite_time_cap_still_halts(tmp_path: Path) -> None:
    old = datetime.now(UTC) - timedelta(minutes=10)
    _arm(tmp_path, created=old)
    decision = autopilot_caps.evaluate_boundary(tmp_path, steps=0, step_cap=None, time_cap_min=5)
    assert decision.proceed is False
    assert decision.halt_kind == "time_cap"


# ── CLI: absent cap flags = unlimited ───────────────────────────────────────


def test_boundary_cli_without_cap_flags_is_unlimited(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    _arm(tmp_path, created=datetime.now(UTC))
    rc = autopilot_caps.main(["boundary", "--root", str(tmp_path), "--current", "research"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["proceed"] is True
    assert out["next_stage"] == "spec"


# ── boundedness invariant: unlimited still terminates within pipeline length ─


def test_unlimited_run_terminates_within_pipeline_length(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-003: with caps removed, the pipeline finiteness + wrapup merge-gate is the bound.

    Advancing repeatedly with NO caps must still stop (merge_gate before wrapup or
    pipeline_complete) in at most len(pipeline) boundary calls — the marker is cleared,
    so a subsequent call kill-switches. No infinite chain.
    """
    import json

    _arm(tmp_path, created=datetime.now(UTC))
    stages = [s.value for s in _PIPELINE]
    current = "research"
    terminated = False
    for _ in range(len(stages) + 1):
        # `--judgment-gate clear` because this test walks a CLEAN pipeline: B3 made the flag
        # fail-closed, so an omitted flag halts at plan and review by design, and this loop
        # is asserting termination-by-pipeline-length, not gate behaviour.
        autopilot_caps.main(
            [
                "boundary",
                "--root",
                str(tmp_path),
                "--current",
                current,
                "--judgment-gate",
                "clear",
            ]
        )
        out = json.loads(capsys.readouterr().out)
        if not out["proceed"]:
            # merge_gate (wrapup) or kill_switch (marker cleared) — terminal.
            assert out["halt_kind"] in ("merge_gate", "kill_switch", "step_cap", "time_cap")
            terminated = True
            break
        current = out["next_stage"]
    assert terminated, "unlimited autopilot must terminate via pipeline bound, not loop forever"


# ── serialize-to-consumed-file: None caps + persistent survive round-trip ────


def test_synth_render_reload_none_caps_and_persistent(tmp_path: Path) -> None:
    from harness_maker.interview import answers_from_harness_yaml

    answers_in = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE],
        autonomy=AutonomyConfig(
            level="auto_safe", step_cap=None, time_cap_min=None, autopilot_persistent=True
        ),
    )
    bp = synthesize(ProjectProfile(), answers_in)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    body = (tmp_path / "harness.yaml").read_text(encoding="utf-8")
    # None must render as YAML null, never the Python repr 'None'.
    assert "step_cap: null" in body
    assert "time_cap_min: null" in body
    assert "autopilot_persistent: true" in body

    restored = answers_from_harness_yaml(tmp_path / "harness.yaml")
    assert restored is not None
    assert restored.autonomy.step_cap is None
    assert restored.autonomy.time_cap_min is None
    assert restored.autonomy.autopilot_persistent is True
