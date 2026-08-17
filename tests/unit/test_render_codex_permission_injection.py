"""Second-opinion sandbox-escape permission after the main-loop cutover.

PLAN-second-opinion-multi-model ADR-011 (generalizes PLAN-codex-second-opinion-sandbox
ADR-002/003/004): the main loop (stage prompt), not a tool-restricted reviewer
subagent, runs `codex exec` / `agy`. So:
- reviewer agents NEVER carry the `Bash` tool or a frontmatter `Bash(codex exec:*)` /
  `Bash(agy --sandbox --print:*)` permission (enabled or disabled) — they revert to
  `Read, Grep, Glob`.
- the `Bash(codex exec:*)` allow rule moves to `settings.json`, gated on
  `'codex' in config.second_opinion.models`; `Bash(agy --sandbox --print:*)` gated on
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
_AGY_MARKER = "Bash(agy --sandbox --print:*)"


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


# ── scoped invoker grant (REVIEW-2026-07-25 F6) ──────────────────────────────

_INVOKER_PREFIX = "Bash(uv run --with "
_INVOKER_SUFFIX = " hm second_opinion_invoke:*)"


def _invoker_rules(settings: dict[str, object]) -> list[str]:
    allow = settings["permissions"]["allow"]  # type: ignore[index]
    return [r for r in allow if _INVOKER_SUFFIX in r]


def test_scoped_invoker_allow_rule_ships_whenever_any_model_is_enabled(tmp_path: Path) -> None:
    """F6: the sandbox-escape instruction must be able to name a rule that covers
    exactly the invoker, so removing the blanket `Bash(uv:*)` cannot break the second
    opinion. Gated on the model SET, not on any single model — an antigravity-only
    harness runs the same invoker.
    """
    for models in (["codex"], ["antigravity"], ["codex", "antigravity"]):
        root = _render(tmp_path / "-".join(models), models=models)
        settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
        rules = _invoker_rules(settings)
        assert len(rules) == 1, f"models={models}: {rules}"
        assert rules[0].startswith(_INVOKER_PREFIX), rules[0]


def test_scoped_invoker_allow_rule_absent_when_no_model_is_enabled(tmp_path: Path) -> None:
    root = _render(tmp_path, models=[])
    assert _invoker_rules(json.loads((root / "settings.json").read_text(encoding="utf-8"))) == []


def test_partials_do_not_claim_the_blanket_uv_rule_authorises_the_escape(
    tmp_path: Path,
) -> None:
    """F6: the prose used to cite the blanket `Bash(uv:*)` as what pre-approves a
    sandbox escape. Naming a blanket grant as the authority for an escape is what made
    the pairing invisible.

    The invariant asserted here is **cross-artifact consistency**: the rule the prose
    names must actually be shipped in the rendered settings. An earlier version of this
    test pinned the sentence "not yet the operative grant" instead, and rewording that
    sentence correctly — after the blanket was retired — turned it red. That is
    `[fail:test] test-pins-retired-implementation-name`, recorded the same day and then
    reproduced here; the assertion is now on the artifact relationship, which survives
    any rewording that keeps the claim true.
    """
    root = _render(tmp_path, models=["codex", "antigravity"])
    body = (root / "commands" / "hm" / "review.md").read_text(encoding="utf-8")
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    allow = settings["permissions"]["allow"]

    # The prose abbreviates the long machine-specific path as `…`, so the tie is on the
    # identifying tail (module + the trailing-wildcard form) rather than the full literal.
    tail = "hm second_opinion_invoke:*)"

    assert "dangerouslyDisableSandbox" in body
    assert tail in body, "prose cites no scoped rule"
    assert any(tail in r for r in allow), "prose cites a rule that is not shipped"
    assert "Bash(uv:*)" not in allow, "the blanket grant is back in settings"
