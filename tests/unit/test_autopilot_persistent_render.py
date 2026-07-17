"""PLAN-autopilot-config-surface P2/P3 — render-side wiring for nullable caps + autoarm hook.

The stage-command boundary CLI must OMIT ``--step-cap``/``--time-cap-min`` when the cap is
None (unlimited) and keep them byte-for-byte when bounded. The SessionStart auto-arm hook
must register into the rendered Claude (and Codex-target) hooks.json.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import (
    AutonomyConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render(tmp_path: Path, autonomy: AutonomyConfig, targets: list[Target]) -> Path:
    answers = InterviewAnswers(preset=Preset.PRODUCTION, targets=targets, autonomy=autonomy)
    render(
        synthesize(ProjectProfile(stack=["python"]), answers),
        tmp_path,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return tmp_path


def test_stage_command_omits_cap_flags_when_unlimited(tmp_path: Path) -> None:
    root = _render(
        tmp_path,
        AutonomyConfig(level="auto_safe", step_cap=None, time_cap_min=None),
        [Target.CLAUDE_CODE],
    )
    body = (root / "commands" / "hm" / "execute.md").read_text(encoding="utf-8")
    assert "harness_maker.autopilot_caps boundary" in body
    assert "--current execute" in body
    assert "--step-cap" not in body
    assert "--time-cap-min" not in body


def test_stage_command_keeps_cap_flags_when_bounded(tmp_path: Path) -> None:
    root = _render(
        tmp_path,
        AutonomyConfig(level="auto_safe", step_cap=20, time_cap_min=300),
        [Target.CLAUDE_CODE],
    )
    body = (root / "commands" / "hm" / "execute.md").read_text(encoding="utf-8")
    assert "--step-cap 20" in body
    assert "--time-cap-min 300" in body


def test_settings_json_registers_autoarm(tmp_path: Path) -> None:
    # `.claude/hooks/hooks.json` is retired (ADR-005, PLAN-permission-deny-and-hooks-wiring):
    # Claude Code reads project hooks ONLY from settings.json, where the SessionStart
    # autoarm hook now lives.
    root = _render(tmp_path, AutonomyConfig(), [Target.CLAUDE_CODE])
    body = (root / "settings.json").read_text(encoding="utf-8")
    assert "autopilot_autoarm" in body


def test_codex_hooks_json_registers_autoarm() -> None:
    # The codex hooks template renders via direct Jinja (mirrors test_codex_hooks_version.py);
    # the full pipeline's `.codex/` routing needs extra synthesize wiring not exercised here.
    from harness_maker.models import HarnessConfig
    from harness_maker.render import _make_env

    env = _make_env()
    cfg = HarnessConfig().model_dump(mode="json")
    rendered = env.get_template("codex/hooks.json.j2").render(
        harness_maker_src_path="/x/0.0.0",
        config=cfg,
        preset="Production",
        is_codex=False,
        skills={},
        stack=[],
        scale="",
        lifecycle="",
    )
    assert "autopilot_autoarm" in rendered
