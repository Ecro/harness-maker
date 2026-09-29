"""Shared renders for SPEC-top-issues-2026-09's template tests — one render per target set."""

from __future__ import annotations

import tempfile
from functools import cache
from pathlib import Path

import pytest

from harness_maker.models import (
    InstrumentationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from .conftest import pin_install_ref


@cache
def rendered(with_codex: bool, *, ledger: bool = False) -> dict[str, str]:
    """Map of `<variant>:<name>` → body for the stage commands/skills these tests read.

    `claude:<stage>` is `.claude/commands/hm/<stage>.md`, `codex:<stage>` is
    `.agents/skills/hm-<stage>/SKILL.md`, and `skill:<name>` is `.claude/skills/<name>/SKILL.md`.
    `ledger` turns on `instrumentation.stage_agent_ledger`, the only arm that renders
    `persist-payload` — off by default, as in a consuming project.
    """
    targets = [Target.CLAUDE_CODE, Target.CODEX] if with_codex else [Target.CLAUDE_CODE]
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        with pytest.MonkeyPatch.context() as mp:
            pin_install_ref(mp)
            render(
                synthesize(
                    ProjectProfile(),
                    InterviewAnswers(
                        preset=Preset.PRODUCTION,
                        targets=targets,
                        worktree={"feature_branch_workflow": True},
                        instrumentation=InstrumentationConfig(stage_agent_ledger=ledger),
                    ),
                ),
                root / ".claude",
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        out: dict[str, str] = {}
        for p in (root / ".claude" / "commands" / "hm").glob("*.md"):
            out[f"claude:{p.stem}"] = p.read_text(encoding="utf-8")
        for p in (root / ".agents" / "skills").glob("hm-*/SKILL.md"):
            out[f"codex:{p.parent.name.removeprefix('hm-')}"] = p.read_text(encoding="utf-8")
        for p in (root / ".claude" / "skills").glob("*/SKILL.md"):
            out[f"skill:{p.parent.name}"] = p.read_text(encoding="utf-8")
        return out


def stage_bodies(stage: str, *, ledger: bool = False) -> list[tuple[str, str]]:
    """The claude and codex renders of one stage, labelled — a test must see both."""
    bodies = rendered(True, ledger=ledger)
    return [(v, bodies[f"{v}:{stage}"]) for v in ("claude", "codex")]


def section(body: str, start: str, end_prefix: str = "\n### ") -> str:
    """Text from the first `start` up to the next heading at `end_prefix`."""
    i = body.index(start)
    j = body.find(end_prefix, i + len(start))
    return body[i : j if j != -1 else len(body)]
