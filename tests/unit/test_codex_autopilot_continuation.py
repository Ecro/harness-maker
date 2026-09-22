"""S7: the actual Codex stage renders must carry an actionable, gated continuation.

These structural contracts supplement real boundary E2E tests and independent
workflow review; they do not prove model obedience. No negative-only false REDs:
every case requires the formerly absent continuation block first.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.models import AutonomyConfig, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

STAGES = ("research", "spec", "execute", "review", "verify", "wrapup")


@pytest.fixture(scope="module")
def outputs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    result = {}
    for level in ("auto_safe", "auto_full", "gated"):
        root = tmp_path_factory.mktemp(level)
        answers = InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CODEX, Target.CLAUDE_CODE],
            autonomy=AutonomyConfig(level=level),
        )
        render(
            synthesize(ProjectProfile(), answers), root / ".claude", freeze_time=DEFAULT_FREEZE_TIME
        )
        result[level] = root
    return result


def _body(root: Path, stage: str) -> str:
    return (root / ".agents/skills" / f"hm-{stage}/SKILL.md").read_text()


def _advance(body: str) -> str:
    return body.split("<!-- @hm:autopilot-advance -->", 1)[1].split(
        "<!-- @hm:/autopilot-advance -->", 1
    )[0]


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("level", ["auto_safe", "auto_full"])
def test_s7_boundary_precedes_codex_skill_execution(
    outputs: dict[str, Path], stage: str, level: str
) -> None:
    block = _advance(_body(outputs[level], stage))
    assert f"hm autopilot_caps boundary --root . --current {stage}" in block
    assert '--session-id \\"$HM_SESSION_ID\\"' in block or '--session-id "$HM_SESSION_ID"' in block
    command = next(
        line for line in block.splitlines() if "Bash(" in line and "caps boundary" in line
    )
    assert "!uv run" not in command
    assert "Append this task's slug as --slug" in block
    assert block.index("caps boundary") < block.index("`proceed: true`")
    success = block.split("<!-- @hm:codex-proceed -->", 1)[1].split(
        "<!-- @hm:/codex-proceed -->", 1
    )[0]
    for obligation in (
        "Only on `proceed: true`, read `.agents/skills/hm-<next_stage>/SKILL.md`",
        "Use next_stage and task_slug from the returned JSON, not another task or a guessed stage",
        "Execute that skill now in the same conversation; do not ask for "
        "routine next-stage confirmation",
        "If the skill is missing in the task worktree, check the base "
        "project and the session skill catalog",
        "If still missing, STOP with an actionable handoff; never claim execution",
    ):
        assert obligation in " ".join(success.split())
    assert "Skill(" not in block


@pytest.mark.parametrize("stage", STAGES)
def test_s7_halt_and_judgment_controls_survive(outputs: dict[str, Path], stage: str) -> None:
    block = _advance(_body(outputs["auto_safe"], stage))
    text = " ".join(block.split())
    assert (
        "If this session has an active loop, return control to its driver; do not auto-advance here"
        in text
    )
    assert (
        "On `proceed: false`, STOP; step_cap, time_cap and merge_gate "
        "are not permission to continue" in text
    )
    if stage in ("spec", "review"):
        assert "--judgment-gate" in block
        assert "Classify as `clear`, `pending` or `blocked` before calling the boundary" in text
        assert "Never downgrade a failed quality check to pending" in text
        assert "Record judgment_directive when judgment_auto_answered is true" in text
    else:
        assert "--judgment-gate" not in block
        assert "If the mandatory gate is unresolved or failed, run gate-blocked and STOP" in text
        assert "caps gate-blocked" in block


def test_s7_gated_negative_control_while_claude_keeps_native_dispatch(
    outputs: dict[str, Path],
) -> None:
    # Positive sibling in this same test forces the new behavior; gated is its control.
    assert ".agents/skills/hm-<next_stage>/SKILL.md" in _advance(
        _body(outputs["auto_safe"], "execute")
    )
    for stage in STAGES:
        assert "@hm:autopilot-advance" not in _body(outputs["gated"], stage)
        claude = (outputs["auto_safe"] / ".claude/commands/hm" / f"{stage}.md").read_text()
        assert re.search(r"Skill\(hm:<next_stage", _advance(claude))


def test_s7_missing_or_invalid_slug_stops_before_skill_dispatch(outputs: dict[str, Path]) -> None:
    block = _advance(_body(outputs["auto_safe"], "research"))
    obligation = (
        "If a required slug is absent or invalid, STOP and request the missing/corrected input"
    )
    assert obligation in " ".join(block.split())
    assert block.index(obligation) < block.index("Execute that skill now")
    assert "Validate task_slug as a string" in block
    assert "[A-Za-z0-9][A-Za-z0-9._-]{0,127}" in block


@pytest.mark.parametrize("end", ["wrapup", None])
def test_auto_answer_is_recorded_before_a_terminal_halt(
    outputs: dict[str, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str], end: str | None
) -> None:
    from harness_maker import autopilot, autopilot_caps
    from harness_maker.models import AtomicStage

    pipeline = [AtomicStage.REVIEW] + ([AtomicStage.WRAPUP] if end else [])
    autopilot.write(tmp_path, level="auto_full", pipeline=pipeline)
    assert (
        autopilot_caps.main(
            [
                "boundary",
                "--root",
                str(tmp_path),
                "--current",
                "review",
                "--judgment-gate",
                "pending",
            ]
        )
        == 0
    )
    import json

    result = json.loads(capsys.readouterr().out)
    assert result["proceed"] is False
    assert result["judgment_auto_answered"] is True
    assert result["halt_kind"] == ("merge_gate" if end else None)
    assert result["pipeline_complete"] is (end is None)
    assert result["judgment_directive"]
    block = _advance(_body(outputs["auto_full"], "review"))
    assert block.index("Record judgment_directive") < block.index("On `proceed: false`, STOP")
    assert "even when proceed is false" in block
