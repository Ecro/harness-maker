"""Second-opinion sandbox-escape permission after the main-loop cutover.

PLAN-second-opinion-multi-model ADR-011 (generalizes PLAN-codex-second-opinion-sandbox
ADR-002/003/004): the main loop (stage prompt), not a tool-restricted reviewer
subagent, runs `codex exec` / `agy`. So:
- reviewer agents NEVER carry the `Bash` tool or a frontmatter `Bash(codex exec:*)` /
  `Bash(agy --print --sandbox:*)` permission (enabled or disabled) — they revert to
  `Read, Grep, Glob`.
- the `Bash(codex exec:*)` allow rule moves to `settings.json`, gated on
  `'codex' in config.second_opinion.models`; `Bash(agy --print --sandbox:*)` gated on
  `'antigravity' in config.second_opinion.models`.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.models import (
    InterviewAnswers,
    Preset,
    ProjectProfile,
    SecondOpinionConfig,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_REVIEWERS = ("code-reviewer", "consensus-arbiter", "plan-validator")
_CODEX_MARKER = "Bash(codex exec:*)"
_AGY_MARKER = "Bash(agy --print --sandbox:*)"


def _render(tmp_path: Path, *, models: list[str], preset: Preset = Preset.SIDE) -> Path:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=preset,
            targets=[Target.CLAUDE_CODE],
            second_opinion=SecondOpinionConfig(models=models),  # type: ignore[arg-type]
        ),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def _tools_tokens(text: str) -> list[str]:
    line = next((ln for ln in text.splitlines() if ln.startswith("tools:")), "")
    return [t.strip() for t in line.removeprefix("tools:").split(",")]


def test_reviewers_never_carry_bash_tool_when_enabled(tmp_path: Path) -> None:
    root = _render(tmp_path, models=["codex", "antigravity"])
    for name in _REVIEWERS:
        body = (root / "agents" / f"{name}.md").read_text(encoding="utf-8")
        assert _tools_tokens(body) == ["Read", "Grep", "Glob"], (
            f"{name} tools: should be exactly Read, Grep, Glob — got {_tools_tokens(body)!r}"
        )


def test_reviewers_never_carry_bash_tool_when_disabled(tmp_path: Path) -> None:
    root = _render(tmp_path, models=[])
    for name in _REVIEWERS:
        body = (root / "agents" / f"{name}.md").read_text(encoding="utf-8")
        assert _tools_tokens(body) == ["Read", "Grep", "Glob"]


def test_no_frontmatter_second_opinion_permission_in_agents(tmp_path: Path) -> None:
    """Neither the codex exec nor agy allow rule may live in any agent frontmatter."""
    root = _render(tmp_path, models=["codex", "antigravity"])
    for md_path in (root / "agents").glob("*.md"):
        body = md_path.read_text(encoding="utf-8")
        assert _CODEX_MARKER not in body, (
            f"{md_path.stem} has frontmatter {_CODEX_MARKER!r} — belongs in settings.json"
        )
        assert _AGY_MARKER not in body, (
            f"{md_path.stem} has frontmatter {_AGY_MARKER!r} — belongs in settings.json"
        )


def test_codex_exec_allow_rule_in_settings_when_enabled(tmp_path: Path) -> None:
    root = _render(tmp_path, models=["codex"])
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    assert _CODEX_MARKER in settings["permissions"]["allow"]
    assert _AGY_MARKER not in settings["permissions"]["allow"]


def test_codex_exec_allow_rule_absent_from_settings_when_disabled(tmp_path: Path) -> None:
    root = _render(tmp_path, models=[])
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    assert _CODEX_MARKER not in settings["permissions"]["allow"]
    assert _AGY_MARKER not in settings["permissions"]["allow"]


def test_agy_allow_rule_in_settings_when_antigravity_enabled(tmp_path: Path) -> None:
    root = _render(tmp_path, models=["antigravity"])
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    assert _AGY_MARKER in settings["permissions"]["allow"]
    assert _CODEX_MARKER not in settings["permissions"]["allow"]


def test_both_allow_rules_present_when_both_models_enabled(tmp_path: Path) -> None:
    root = _render(tmp_path, models=["codex", "antigravity"])
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    assert _CODEX_MARKER in settings["permissions"]["allow"]
    assert _AGY_MARKER in settings["permissions"]["allow"]
