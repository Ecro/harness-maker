"""Retirement repair: preserve the configured critic across load and rendering.

The unchanged/custom allowlist cases are negative invariants, intentionally green
before the fix: they reject appending spec-validator unconditionally. The positive
retired-name cases require the migration and reject dropping the old entry instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import Preset, ProjectProfile, SecondOpinionConfig, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.mark.parametrize(
    ("agents", "expected"),
    [
        (
            ["custom", "plan-validator", "code-reviewer"],
            ["custom", "spec-validator", "code-reviewer"],
        ),
        (["plan-validator", "spec-validator", "custom"], ["spec-validator", "custom"]),
        (["spec-validator", "custom", "plan-validator"], ["spec-validator", "custom"]),
        (["custom", "custom", "plan-validator"], ["custom", "custom", "spec-validator"]),
        ([], []),
        (["custom-plan-validator", "custom"], ["custom-plan-validator", "custom"]),
    ],
)
def test_retired_agent_migration_preserves_allowlist(
    agents: list[str], expected: list[str]
) -> None:
    original = list(agents)
    first = SecondOpinionConfig(agents=agents)
    assert first.agents == expected
    assert agents == original
    assert first.models == []  # dormant preferences migrate without enabling a provider
    second = SecondOpinionConfig.model_validate(first.model_dump())
    assert second.model_dump() == first.model_dump()


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("preset", [Preset.SIDE, Preset.PRODUCTION])
def test_saved_retired_agent_reaches_generated_critic(
    tmp_path: Path, legacy: bool, preset: Preset
) -> None:
    config = tmp_path / "saved.yaml"
    opinion = (
        {"enabled": True, "agents": ["custom", "plan-validator"], "hermetic": False}
        if legacy
        else {
            "models": ["claude"],
            "agents": ["custom", "plan-validator"],
            "claude": {"model": "sonnet", "timeout": 123.0},
        }
    )
    key = "codex_second_opinion" if legacy else "second_opinion"
    config.write_text(yaml.safe_dump({"preset": preset.value, "targets": ["codex"], key: opinion}))
    answers = answers_from_harness_yaml(config)
    assert answers is not None
    assert answers.second_opinion.agents == ["custom", "spec-validator"]
    assert answers.targets == [Target.CODEX]
    destination = tmp_path / "generated"
    render(
        synthesize(ProjectProfile(), answers),
        destination / ".claude",
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    critic = (destination / ".codex/agents/spec-validator.toml").read_text()
    assert "<!-- @hm:second-opinion-reconcile -->" in critic
    assert "second_opinion_results" in critic
    restored = answers_from_harness_yaml(destination / ".claude/harness.yaml")
    assert restored is not None
    assert restored.second_opinion.model_dump() == answers.second_opinion.model_dump()
    if legacy:
        assert restored.second_opinion.codex.hermetic is False
    else:
        assert restored.second_opinion.claude.model == "sonnet"
        assert restored.second_opinion.claude.timeout == 123.0


@pytest.mark.parametrize("models", [["claude"], ["codex", "antigravity", "claude"]])
def test_critic_output_accepts_every_enabled_model(models: list[str]) -> None:
    from harness_maker.models import HarnessConfig
    from harness_maker.render import _make_env

    opinion = SecondOpinionConfig.model_validate({"models": models})
    config = HarnessConfig(second_opinion=opinion).model_dump(mode="json")
    text = (
        _make_env()
        .get_template("agents/spec-validator_body.md.j2")
        .render(name="spec-validator", config=config, communication_variant="full", is_codex=True)
    )
    declaration = re.search(r'"model":\s*(.*?),\s*"status":', text)
    assert declaration is not None
    declared = re.findall(r'"([a-z]+)"', declaration.group(1))
    assert declared == models
