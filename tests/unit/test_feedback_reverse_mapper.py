"""Phase 1 — answers_from_harness_yaml round-trip for feedback.enabled.

PLAN-auto-feedback-2026-05 CLAUDE.md checkpoint 6.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from harness_maker import interview
from harness_maker.models import InterviewAnswers


def _answers_from_yaml(text: str, tmp_path: Path) -> InterviewAnswers | None:
    p = tmp_path / "harness.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return interview.answers_from_harness_yaml(p)


def test_feedback_absent_silent_default_false(tmp_path: Path) -> None:
    """Old harness.yaml without `feedback:` key → silent default false (no warning, no None return).
    CLAUDE.md checkpoint 6: schema gap handled by default fallback."""
    yaml_text = """
        preset: Side
        locale: en
        targets: [claude-code]
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    assert answers is not None
    assert answers.feedback.enabled is False


def test_feedback_enabled_true_round_trip(tmp_path: Path) -> None:
    """harness.yaml with feedback.enabled=true → InterviewAnswers.feedback.enabled=true."""
    yaml_text = """
        preset: Side
        locale: en
        targets: [claude-code]
        feedback:
          enabled: true
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    assert answers is not None
    assert answers.feedback.enabled is True


def test_feedback_enabled_false_explicit_round_trip(tmp_path: Path) -> None:
    """Explicit false survives the round-trip."""
    yaml_text = """
        preset: Production
        locale: ko
        targets: [claude-code, cursor]
        feedback:
          enabled: false
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    assert answers is not None
    assert answers.feedback.enabled is False


def test_feedback_malformed_value_falls_back(tmp_path: Path) -> None:
    """Non-bool value → tolerant fallback to default false; OTHER fields parse normally.

    Distinguishes 3 implementation paths the assertion must constrain:
    (A) tolerant fallback (PLAN intent) → all asserts pass
    (B) silent coerce "yes" → True → final assert fails
    (C) uncaught ValidationError → answers is None → second assert fails
    Per test-reviewer Phase A.5 round 1 critique (tautology).
    """
    yaml_text = """
        preset: Side
        locale: en
        targets: [claude-code]
        feedback:
          enabled: "yes"
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    # (C) guard — exception in feedback parse must NOT poison the whole load.
    assert answers is not None
    # Tolerant: OTHER fields from the same yaml parse normally despite malformed feedback.
    assert answers.locale == "en"
    assert answers.preset.value == "Side"
    # (B) guard — must not silently coerce "yes" → True.
    assert answers.feedback.enabled is False


def test_feedback_section_non_dict_falls_back(tmp_path: Path) -> None:
    """`feedback: [whatever]` (list, not dict) → tolerant: default false."""
    yaml_text = """
        preset: Side
        locale: en
        targets: [claude-code]
        feedback: [1, 2]
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    assert answers is not None
    assert answers.feedback.enabled is False
