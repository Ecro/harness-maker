"""The autopilot picker must be true in every runtime it renders into.

Two different capabilities used to sit under one "Claude Code only" label:

- **Arming** writes a marker file. Nothing about that is runtime-specific, and
  `hm autopilot on --session-id ""` arms the shared degraded marker from any runtime
  (verified by hand against a Codex session, 2026-08-16).
- **Auto-advance** invokes the next stage through the `Skill` tool, which Cursor and Codex
  do not have. That one really is Claude-Code-only.

Collapsing them made the picker read as inapplicable to Codex, so a Codex session read its
own rendered skill, believed autopilot was unavailable, and stood down — while the CLI it
would have called worked the whole time. The label was the bug; nothing was missing.
"""

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
    codex = (out / ".." / ".agents" / "skills" / "hm-plan" / "SKILL.md").resolve()
    return {
        "claude": (out / "commands" / "hm" / "plan.md").read_text(encoding="utf-8"),
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
            "file write and works everywhere; only auto-advance needs the Skill tool."
        )


def test_the_picker_separates_arming_from_auto_advance(bodies: dict[str, str]) -> None:
    """Both halves, because dropping the label without the distinction is the other failure.

    Saying only "autopilot works in Codex" would be wrong in the opposite direction: stages
    do NOT chain themselves there. The block has to carry both facts or it trades one wrong
    reading for another.
    """
    for runtime, body in bodies.items():
        assert "Arming works in any runtime" in body, f"{runtime}: arming not stated"
        limit = f"{runtime}: the auto-advance limit is not stated, so a Codex reader will "
        assert "Skill" in body, limit + "expect stages to chain themselves"
        assert "auto-advance" in body.lower(), limit + "not know what needs the Skill tool"


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


def test_auto_advance_stays_claude_code_only(bodies: dict[str, str]) -> None:
    """The half that IS runtime-specific must not be broadened by a future edit here.

    Auto-advance calls the next stage through the `Skill` tool. Telling a Codex session it
    auto-advances would leave it waiting for a chain that cannot happen.
    """
    claude = bodies["claude"]
    assert "@hm:autopilot-advance" in claude
    assert "Claude" in claude
