"""Arming and native stage dispatch are accurately described for both runtimes."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def bodies() -> dict[str, str]:
    """The plan stage as each runtime receives it."""
    profile = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CODEX]
    out = Path(tempfile.mkdtemp()) / "out"
    render(synthesize(profile, answers), out, freeze_time=DEFAULT_FREEZE_TIME)
    codex = (out / ".." / ".agents" / "skills" / "hm-spec" / "SKILL.md").resolve()
    return {
        "claude": (out / "commands" / "hm" / "spec.md").read_text(encoding="utf-8"),
        "codex": codex.read_text(encoding="utf-8"),
    }


def test_the_picker_reaches_the_codex_stage_skill_at_all(bodies: dict[str, str]) -> None:
    """Non-vacuity for every assertion below — they are all about ITS text."""
    for runtime, body in bodies.items():
        assert "@hm:autopilot-picker" in body, f"{runtime}: no autopilot picker rendered"


def test_the_picker_is_not_labelled_claude_code_only(bodies: dict[str, str]) -> None:
    """The exact string that made a Codex session stand down.

    Asserted as a literal because that is what the reading agent keys on: a parenthetical in
    the FIRST line of the block, before any of the branch logic it would otherwise follow.
    """
    for runtime, body in bodies.items():
        assert "Autopilot session start (Claude Code only)" not in body, (
            f"{runtime}: the picker claims to be Claude-Code-only again. Arming is a marker "
            "file write and works everywhere."
        )


def test_the_picker_names_native_continuation(bodies: dict[str, str]) -> None:
    for body in bodies.values():
        assert "Arming works in any runtime" in body
        assert "Codex's next-skill read/execute procedure" in body
        assert "Cursor retains the handoff path" in body


def test_the_degraded_branch_calls_codex_normal_rather_than_broken(
    bodies: dict[str, str],
) -> None:
    """`degraded-idless` in Cursor/Codex is the design, not a hook failure.

    The previous text attributed it solely to a WSL2 SessionStart failure, so a Codex reader
    hitting the NORMAL case was told it was in a broken state — and a broken state is a
    reason to stop rather than arm.
    """
    for runtime, body in bodies.items():
        assert "NORMAL state, not a failure" in body, (
            f"{runtime}: degraded case still reads as broken"
        )
        # Asserted on a phrase that cannot straddle a line break: the block is a markdown
        # blockquote, so any multi-word claim may wrap and pick up a "> " prefix mid-phrase.
        # (Two assertions today already failed for exactly that reason, not for content.)
        assert "arms the shared degraded marker" in body, (
            f"{runtime}: the degraded branch does not say to arm"
        )


def test_claude_retains_skill_dispatch(bodies: dict[str, str]) -> None:
    assert "Skill(hm:<next_stage" in bodies["claude"]


def test_codex_gets_picker_and_native_auto_advance(bodies: dict[str, str]) -> None:
    codex = bodies["codex"]
    assert "@hm:autopilot-picker" in codex
    assert "@hm:autopilot-advance" in codex
    assert ".agents/skills/hm-<next_stage>/SKILL.md" in codex
    assert "Skill(hm:<next_stage" not in codex
