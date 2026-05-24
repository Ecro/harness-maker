"""Tests for CodexSecondOpinionConfig + HarnessConfig/InterviewAnswers integration.

Phase 1 of PLAN-codex-second-llm-integration. ADR-002 defaults: enabled=False,
agents=[code-reviewer, consensus-arbiter, plan-validator]. ADR-003 failure
policy. ADR-006 hermetic. ADR-005 output_schema_path. Validator P0#3 fix:
InterviewAnswers also extends (extra='forbid' would reject otherwise).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness_maker.models import (
    CodexSecondOpinionConfig,
    HarnessConfig,
    InterviewAnswers,
    Target,
)


def test_codex_second_opinion_config_defaults() -> None:
    cfg = CodexSecondOpinionConfig()
    assert cfg.enabled is False
    assert cfg.agents == ["code-reviewer", "consensus-arbiter", "plan-validator"]
    assert cfg.failure_policy == "warn-and-proceed"
    assert cfg.hermetic is True
    assert cfg.output_schema_path == ".claude/schemas/codex-finding.schema.json"


def test_codex_second_opinion_config_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CodexSecondOpinionConfig(unknown_field="x")  # type: ignore[call-arg]


def test_harness_config_round_trip_with_codex_second_opinion() -> None:
    cfg = HarnessConfig(
        codex_second_opinion=CodexSecondOpinionConfig(enabled=True),
    )
    dumped = cfg.model_dump()
    restored = HarnessConfig.model_validate(dumped)
    assert restored.codex_second_opinion.enabled is True
    assert restored.codex_second_opinion.agents == [
        "code-reviewer",
        "consensus-arbiter",
        "plan-validator",
    ]


def test_harness_config_default_codex_second_opinion_disabled() -> None:
    cfg = HarnessConfig()
    assert cfg.codex_second_opinion.enabled is False


def test_interview_answers_round_trip_with_codex_second_opinion() -> None:
    answers = InterviewAnswers(
        codex_second_opinion=CodexSecondOpinionConfig(enabled=True, hermetic=False),
    )
    dumped = answers.model_dump()
    restored = InterviewAnswers.model_validate(dumped)
    assert restored.codex_second_opinion.enabled is True
    assert restored.codex_second_opinion.hermetic is False


def test_interview_answers_default_codex_second_opinion_disabled() -> None:
    answers = InterviewAnswers()
    assert answers.codex_second_opinion.enabled is False


def test_codex_second_opinion_failure_policy_literal_enforced() -> None:
    with pytest.raises(ValidationError):
        CodexSecondOpinionConfig(failure_policy="bogus")  # type: ignore[arg-type]


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
    assert cfg.codex_second_opinion.enabled is False
