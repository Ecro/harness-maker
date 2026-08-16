"""`is_codex` must agree with where the rendered file actually lands.

The context builder used to hard-code `is_codex: False` for every file it produced, on the
stated grounds that "Codex skill bodies are pre-rendered in `_codex_stage_skills()`". Half
true, and the wrong half was invisible: the stage BODY is pre-rendered with `is_codex=True`,
but the WRAPPER around it — `codex/stage_skill.md.j2` and the partials it includes — is
rendered by the builder, so every Codex file on disk was produced with the flag saying it was
not Codex. A wrapper-level partial branching on `is_codex` read as Codex-aware in its own
source and silently took the Claude arm.

That is not a hypothesis. `step_manifest.md.j2` gated the autopilot picker on
`not is_codex`, and the picker rendered into all seven Codex stage skills regardless — which
is how the gate's inertness stayed unnoticed until a Codex session's behaviour was traced by
hand.

This asserts on the BLUEPRINT rather than on template text, because the defect lived in the
context, not the templates: every render-grep over the output passed the whole time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile, Target
from harness_maker.synthesize import _is_codex_output, synthesize


@pytest.fixture(scope="module")
def entries() -> list[tuple[str, bool]]:
    """(out_path, is_codex) for a harness targeting every runtime at once."""
    profile = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    return [
        (str(fe.path), bool(fe.context.get("is_codex")))
        for fe in synthesize(profile, answers).files
    ]


def _codex_destined(out_path: str) -> bool:
    """Independent of the production predicate — a copy of it would assert nothing."""
    parts = Path(out_path).parts
    return bool(parts) and (parts[0] in {".codex", ".agents"} or out_path == "AGENTS.md")


def test_the_blueprint_actually_contains_codex_files(entries: list[tuple[str, bool]]) -> None:
    """Non-vacuity: without Codex outputs the parity test below passes trivially."""
    assert [p for p, _ in entries if _codex_destined(p)], "no Codex-destined files rendered"


def test_every_codex_destined_file_is_flagged_as_codex(entries: list[tuple[str, bool]]) -> None:
    wrong = sorted(p for p, flag in entries if _codex_destined(p) and not flag)
    assert not wrong, (
        f"{len(wrong)} Codex-destined file(s) render with is_codex=False, so any `is_codex` "
        f"branch in them takes the Claude arm: {wrong[:8]}"
    )


def test_no_claude_or_cursor_file_is_flagged_as_codex(entries: list[tuple[str, bool]]) -> None:
    """The converse: a mis-flagged shared file would emit Codex syntax to Claude users."""
    wrong = sorted(p for p, flag in entries if flag and not _codex_destined(p))
    assert not wrong, f"non-Codex file(s) flagged is_codex=True: {wrong[:8]}"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (".codex/hooks.json", True),
        (".agents/skills/hm-plan/SKILL.md", True),
        ("AGENTS.md", True),
        ("commands/hm/plan.md", False),
        ("agents/code-reviewer.md", False),  # `agents/`, NOT `.agents/` — one dot apart
        ("skills/context-linter/SKILL.md", False),
        ("", False),
    ],
)
def test_the_predicate_itself(path: str, expected: bool) -> None:
    """`agents/` vs `.agents/` is the whole difference between shared and Codex-only."""
    assert _is_codex_output(path) is expected
