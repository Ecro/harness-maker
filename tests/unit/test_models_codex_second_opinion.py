"""Tests for SecondOpinionConfig + HarnessConfig/InterviewAnswers integration.

PLAN-second-opinion-multi-model: supersedes the single-vendor
CodexSecondOpinionConfig (Phase 1 of PLAN-codex-second-llm-integration). ADR-002
defaults: models=[] (feature off), agents=[code-reviewer, consensus-arbiter,
plan-validator]. ADR-003 failure policy. ADR-006 hermetic (now nested under
``codex``). ADR-005 output_schema_path (now nested under ``codex``, filename
renamed to second-opinion-finding.schema.json). Validator P0#3 fix:
InterviewAnswers also extends (extra='forbid' would reject otherwise).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness_maker.models import (
    HarnessConfig,
    InterviewAnswers,
    SecondOpinionConfig,
    Target,
)


def test_second_opinion_config_defaults() -> None:
    cfg = SecondOpinionConfig()
    assert cfg.enabled is False
    assert cfg.models == []
    assert cfg.agents == ["code-reviewer", "consensus-arbiter", "plan-validator"]
    assert cfg.failure_policy == "warn-and-proceed"
    assert cfg.codex.hermetic is True
    assert cfg.codex.output_schema_path == ".claude/schemas/second-opinion-finding.schema.json"
    assert cfg.antigravity.model == "Gemini 3.1 Pro (High)"


def test_second_opinion_config_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SecondOpinionConfig(unknown_field="x")  # type: ignore[call-arg]


def test_harness_config_round_trip_with_second_opinion() -> None:
    cfg = HarnessConfig(
        second_opinion=SecondOpinionConfig(models=["codex"]),
    )
    dumped = cfg.model_dump()
    restored = HarnessConfig.model_validate(dumped)
    assert restored.second_opinion.enabled is True
    assert restored.second_opinion.models == ["codex"]
    assert restored.second_opinion.agents == [
        "code-reviewer",
        "consensus-arbiter",
        "plan-validator",
    ]


def test_harness_config_default_second_opinion_disabled() -> None:
    cfg = HarnessConfig()
    assert cfg.second_opinion.enabled is False
    assert cfg.second_opinion.models == []


def test_interview_answers_round_trip_with_second_opinion() -> None:
    answers = InterviewAnswers(
        second_opinion=SecondOpinionConfig(
            models=["codex"],
            codex={"hermetic": False},  # type: ignore[arg-type]
        ),
    )
    dumped = answers.model_dump()
    restored = InterviewAnswers.model_validate(dumped)
    assert restored.second_opinion.enabled is True
    assert restored.second_opinion.codex.hermetic is False


def test_interview_answers_default_second_opinion_disabled() -> None:
    answers = InterviewAnswers()
    assert answers.second_opinion.enabled is False


def test_second_opinion_failure_policy_literal_enforced() -> None:
    with pytest.raises(ValidationError):
        SecondOpinionConfig(failure_policy="bogus")  # type: ignore[arg-type]


def test_second_opinion_models_literal_enforced() -> None:
    """Only 'codex'/'antigravity' are valid — an unknown model rejects at the type layer."""
    with pytest.raises(ValidationError):
        SecondOpinionConfig(models=["bogus"])  # type: ignore[list-item]


def test_second_opinion_models_deduped_order_preserving() -> None:
    """A repeated model is a config typo, not two votes — de-dupe, keep order."""
    cfg = SecondOpinionConfig(models=["codex", "antigravity", "codex"])
    assert cfg.models == ["codex", "antigravity"]


def test_harness_config_legacy_yaml_without_key_loads_with_default() -> None:
    """Validates ADR-005 P-W2: legacy harness.yaml without the key loads
    cleanly via default_factory (no extra='forbid' violation, no migration).

    Note: strict=True rejects bare strings for enum fields, so the legacy
    fixture passes the Target enum directly. The real round-trip from
    harness.yaml goes through interview.answers_from_harness_yaml which
    converts strings to Target before validation; this test isolates the
    default-factory behavior from the string-coercion layer.
    """
    legacy: dict[str, object] = {
        "locale": "en",
        "targets": [Target.CLAUDE_CODE],
    }
    cfg = HarnessConfig.model_validate(legacy)
    assert cfg.second_opinion.enabled is False
    assert cfg.second_opinion.models == []
