"""Codex sandbox-escape permission after the main-loop cutover.

PLAN-codex-second-opinion-sandbox ADR-002/003/004: the main loop (stage prompt),
not a tool-restricted reviewer subagent, runs `codex exec`. So:
- reviewer agents NEVER carry the `Bash` tool or a frontmatter `Bash(codex exec:*)`
  permission (enabled or disabled) — they revert to `Read, Grep, Glob`.
- the `Bash(codex exec:*)` allow rule moves to `settings.json`, gated on enabled.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.models import (
    CodexSecondOpinionConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_REVIEWERS = ("code-reviewer", "consensus-arbiter", "plan-validator")
_PERMISSION_MARKER = "Bash(codex exec:*)"


def _render(tmp_path: Path, *, enabled: bool, preset: Preset = Preset.SIDE) -> Path:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=preset,
            targets=[Target.CLAUDE_CODE],
            codex_second_opinion=CodexSecondOpinionConfig(enabled=enabled),
        ),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def _tools_tokens(text: str) -> list[str]:
    line = next((ln for ln in text.splitlines() if ln.startswith("tools:")), "")
    return [t.strip() for t in line.removeprefix("tools:").split(",")]


def test_reviewers_never_carry_bash_tool_when_enabled(tmp_path: Path) -> None:
    root = _render(tmp_path, enabled=True)
    for name in _REVIEWERS:
        body = (root / "agents" / f"{name}.md").read_text(encoding="utf-8")
        assert _tools_tokens(body) == ["Read", "Grep", "Glob"], (
            f"{name} tools: should be exactly Read, Grep, Glob — got {_tools_tokens(body)!r}"
        )


def test_reviewers_never_carry_bash_tool_when_disabled(tmp_path: Path) -> None:
    root = _render(tmp_path, enabled=False)
    for name in _REVIEWERS:
        body = (root / "agents" / f"{name}.md").read_text(encoding="utf-8")
        assert _tools_tokens(body) == ["Read", "Grep", "Glob"]


def test_no_frontmatter_codex_exec_permission_in_agents(tmp_path: Path) -> None:
    """The Bash(codex exec:*) allow rule must NOT live in any agent frontmatter."""
    root = _render(tmp_path, enabled=True)
    for md_path in (root / "agents").glob("*.md"):
        assert _PERMISSION_MARKER not in md_path.read_text(encoding="utf-8"), (
            f"{md_path.stem} has frontmatter {_PERMISSION_MARKER!r} — belongs in settings.json"
        )


def test_codex_exec_allow_rule_in_settings_when_enabled(tmp_path: Path) -> None:
    root = _render(tmp_path, enabled=True)
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    assert _PERMISSION_MARKER in settings["permissions"]["allow"]


def test_codex_exec_allow_rule_absent_from_settings_when_disabled(tmp_path: Path) -> None:
    root = _render(tmp_path, enabled=False)
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    assert _PERMISSION_MARKER not in settings["permissions"]["allow"]
