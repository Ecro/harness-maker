"""Phase 1 — FeedbackConfig model + HarnessConfig/InterviewAnswers wiring.

PLAN-auto-feedback-2026-05 ADR-002.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness_maker.models import FeedbackConfig, HarnessConfig, InterviewAnswers


def test_feedback_config_defaults_disabled() -> None:
    """Default enabled=false — ADR-001 opt-in invariant."""
    cfg = FeedbackConfig()
    assert cfg.enabled is False


def test_feedback_config_explicit_true() -> None:
    cfg = FeedbackConfig(enabled=True)
    assert cfg.enabled is True


def test_feedback_config_extra_forbid() -> None:
    """ADR-002: keep schema additive — unknown keys must surface, not silently drop."""
    with pytest.raises(ValidationError):
        FeedbackConfig(enabled=False, unknown_key="oops")  # type: ignore[call-arg]


def test_feedback_config_strict_types() -> None:
    """enabled must be bool, not coerced from str/int."""
    with pytest.raises(ValidationError):
        FeedbackConfig(enabled="true")  # type: ignore[arg-type]


def test_harness_config_feedback_default_factory() -> None:
    """HarnessConfig.feedback defaults to FeedbackConfig() (enabled=false)."""
    hc = HarnessConfig()
    assert isinstance(hc.feedback, FeedbackConfig)
    assert hc.feedback.enabled is False


def test_harness_config_feedback_override() -> None:
    hc = HarnessConfig(feedback=FeedbackConfig(enabled=True))
    assert hc.feedback.enabled is True


def test_interview_answers_feedback_default_factory() -> None:
    """InterviewAnswers mirrors HarnessConfig.feedback default."""
    ia = InterviewAnswers()
    assert isinstance(ia.feedback, FeedbackConfig)
    assert ia.feedback.enabled is False


def test_interview_answers_feedback_round_trip_via_model_copy() -> None:
    """InterviewAnswers.model_copy(update={'feedback': ...}) preserves the change.
    This is the path answers_from_harness_yaml() uses at line 958."""
    base = InterviewAnswers()
    updated = base.model_copy(update={"feedback": FeedbackConfig(enabled=True)})
    assert updated.feedback.enabled is True
    # Original untouched (model_copy contract)
    assert base.feedback.enabled is False
