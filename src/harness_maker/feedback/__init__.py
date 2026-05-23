"""Maintainer-dogfooding feedback drafts (PLAN-auto-feedback-2026-05).

Opt-in via ``harness.yaml.feedback.enabled`` (default off). When on, the
dispatcher wrapper templates emit a Jinja-conditional block that asks the
current turn's LLM to inspect local telemetry, decide whether a harness-self
issue occurred, and if so write a draft to ``.claude/observability/feedback/``
with a footer command for manual ``gh issue create --web`` submission.

Zero socket calls from this module — preserves ``tests/unit/test_no_network.py``
(ADR-005 of PLAN-oss-readiness-audit).
"""

from harness_maker.feedback.draft_writer import FeedbackDraft, TriggerSignal, write
from harness_maker.feedback.footer import render as render_footer
from harness_maker.feedback.telemetry_grep import (
    TELEMETRY_GREP_MAX_BYTES,
    gather_recent_signals,
    last_stop_with_trace,
)

__all__ = [
    "TELEMETRY_GREP_MAX_BYTES",
    "FeedbackDraft",
    "TriggerSignal",
    "gather_recent_signals",
    "last_stop_with_trace",
    "render_footer",
    "write",
]
