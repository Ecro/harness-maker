"""Phase 1 — AgentModelSpec / CodexAgentSpec Pydantic strict-mode + field validation.

ADR-001 + ADR-002: nested per-agent block schema; strict, extra=forbid.
"""

import pytest
from pydantic import ValidationError

from harness_maker.models import (
    AgentModelSpec,
    CodexAgentSpec,
    HarnessConfig,
    InterviewAnswers,
    Preset,
)


def test_codex_agent_spec_all_fields_optional() -> None:
    spec = CodexAgentSpec()
    assert spec.model is None
    assert spec.reasoning_effort is None


def test_codex_agent_spec_reasoning_effort_enum_accepts_valid() -> None:
    for effort in ("none", "minimal", "low", "medium", "high", "xhigh"):
        spec = CodexAgentSpec(reasoning_effort=effort)
        assert spec.reasoning_effort == effort


def test_codex_agent_spec_reasoning_effort_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        CodexAgentSpec(reasoning_effort="extreme")  # not in Literal


def test_codex_agent_spec_strict_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CodexAgentSpec(reasoning_effort="medium", verbosity="high")  # unknown key


def test_agent_model_spec_all_fields_optional() -> None:
    spec = AgentModelSpec()
    assert spec.claude is None
    assert spec.cursor is None
    assert spec.codex is None


def test_agent_model_spec_nested_codex_round_trip() -> None:
    spec = AgentModelSpec(
        claude="opus",
        cursor="claude-4-7-opus",
        codex=CodexAgentSpec(reasoning_effort="high"),
    )
    assert spec.claude == "opus"
    assert spec.cursor == "claude-4-7-opus"
    assert spec.codex is not None
    assert spec.codex.reasoning_effort == "high"
    assert spec.codex.model is None


def test_agent_model_spec_strict_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AgentModelSpec(claude="opus", verbosity="high")  # unknown key


def test_agent_model_spec_partial_fields() -> None:
    """Only one field set is fine — others default to None."""
    spec = AgentModelSpec(claude="sonnet")
    assert spec.claude == "sonnet"
    assert spec.cursor is None
    assert spec.codex is None


# --- Security: YAML injection prevention (review security-reviewer P0 fix) ---


@pytest.mark.parametrize(
    "evil",
    [
        "opus\nallow:\n  - Bash(*:*)",  # newline injection → fake YAML keys
        "haiku # injected comment",  # YAML comment metachar
        "sonnet: child_key",  # injection of nested YAML structure
        "model with spaces",  # space breaks bare scalar
        'opus"with"quotes',  # quote chars
    ],
)
def test_agent_model_spec_rejects_injection_payloads(evil: str) -> None:
    """AgentModelSpec.claude/cursor must reject embedded YAML-significant
    characters that could inject permissions / nested keys when rendered into
    Claude agent frontmatter."""
    with pytest.raises(ValidationError):
        AgentModelSpec(claude=evil)
    with pytest.raises(ValidationError):
        AgentModelSpec(cursor=evil)


@pytest.mark.parametrize(
    "evil",
    [
        "claude-opus-4-7\nextra: smuggled",
        "claude-opus-4-7 # comment",
        "model with spaces",
    ],
)
def test_default_model_rejects_injection_payloads(evil: str) -> None:
    """HarnessConfig.default_model and InterviewAnswers.default_model both
    flow into rendered configs (aider.yml, foreign-config templates) and must
    reject injection payloads at parse time."""
    with pytest.raises(ValidationError):
        HarnessConfig(default_model=evil)
    with pytest.raises(ValidationError):
        InterviewAnswers(default_model=evil)


def test_agent_model_spec_accepts_safe_values() -> None:
    """Positive control: alphanumerics + standard separators pass."""
    AgentModelSpec(claude="opus")
    AgentModelSpec(claude="sonnet")
    AgentModelSpec(claude="haiku")
    AgentModelSpec(cursor="claude-4-7-opus")
    AgentModelSpec(cursor="claude-4-6-sonnet")
    AgentModelSpec(cursor="gpt-5.5")
    AgentModelSpec(cursor="model_with_underscores")


# --- ADR-002 + Phase 1 deviation (AliasChoices back-compat) ---


def test_harness_config_default_model_default_value() -> None:
    """HarnessConfig.default_model defaults to claude-opus-4-7 (replaces recommended_model)."""
    cfg = HarnessConfig()
    assert cfg.default_model == "claude-opus-4-7"


def test_harness_config_default_model_explicit() -> None:
    """Explicit construction via the new canonical field name."""
    cfg = HarnessConfig(default_model="claude-sonnet-4-6")
    assert cfg.default_model == "claude-sonnet-4-6"


def test_harness_config_recommended_model_alias_round_trips_via_model_validate() -> None:
    """ADR-002 + AliasChoices: old harness.yaml `recommended_model:` populates
    new `default_model` field. This is the wire path that every existing user
    relies on at re-render time.
    """
    cfg = HarnessConfig.model_validate(
        {"recommended_model": "claude-opus-4-7", "preset": Preset.PRODUCTION}
    )
    assert cfg.default_model == "claude-opus-4-7"


def test_harness_config_recommended_model_kwarg_populates_default_model() -> None:
    """Direct kwarg form: HarnessConfig(recommended_model="...") still works
    (populate_by_name + AliasChoices). Existing tests rely on this construction."""
    cfg = HarnessConfig(recommended_model="claude-sonnet-4-6")  # type: ignore[call-arg]
    assert cfg.default_model == "claude-sonnet-4-6"


def test_harness_config_default_model_wins_when_both_provided() -> None:
    """Canonical field takes precedence when both new and old keys are present.

    ADR-004 silent migration: the dual-key model_validator drops the deprecated
    recommended_model when default_model is also present (instead of raising
    extra_forbidden under strict mode).
    """
    cfg = HarnessConfig.model_validate(
        {
            "default_model": "claude-opus-4-7",
            "recommended_model": "claude-haiku-4-5",
            "preset": Preset.SIDE,
        }
    )
    assert cfg.default_model == "claude-opus-4-7"


def test_harness_config_recommended_model_property_returns_default_model() -> None:
    """Read-side back-compat: existing callers using cfg.recommended_model
    still get the right value via the deprecated property."""
    cfg = HarnessConfig(default_model="claude-sonnet-4-6")
    assert cfg.recommended_model == "claude-sonnet-4-6"


def test_harness_config_agent_models_default_empty() -> None:
    """New agent_models field defaults to empty dict (preset map fills in)."""
    cfg = HarnessConfig()
    assert cfg.agent_models == {}


def test_harness_config_schema_version_bumped_to_2() -> None:
    """ADR-011: schema_version 1 → 2."""
    cfg = HarnessConfig()
    assert cfg.schema_version == 2


def test_interview_answers_default_model_alias() -> None:
    """Same AliasChoices contract on InterviewAnswers (the interview-side mirror)."""
    answers = InterviewAnswers.model_validate({"recommended_model": "claude-opus-4-7"})
    assert answers.default_model == "claude-opus-4-7"


def test_interview_answers_default_model_wins_when_both_provided() -> None:
    """Mirror of HarnessConfig dual-key precedence test.

    Phase 2 will call InterviewAnswers.model_validate on dicts loaded via
    io_utils.load_harness_yaml — without the dual-key guard on
    InterviewAnswers, a v2 harness.yaml that retains the deprecated
    recommended_model key would raise extra_forbidden (review code-reviewer P1).
    """
    answers = InterviewAnswers.model_validate(
        {
            "default_model": "claude-opus-4-7",
            "recommended_model": "claude-haiku-4-5",
        }
    )
    assert answers.default_model == "claude-opus-4-7"
