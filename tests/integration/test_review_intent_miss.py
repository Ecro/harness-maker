"""Phase 8c scripted integration test: REVIEW hook → intent_miss counter (ADR-008).

Mock-only deterministic test (no INTEGRATION gate) — verifies the cross-stage
contract that REVIEW's mis-specification flagging produces a recorded
silent-intent-miss event when the slot was previously marked common-ground
at LLM-inference ≥0.95.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.observability.intent_miss import (
    IntentMissEvent,
    record_intent_miss,
)


def _mark(
    slot: str,
    *,
    source: str = "LLM-inferred",
    confidence: float = 0.97,
) -> dict[str, Any]:
    return {
        "slot": slot,
        "source": source,
        "confidence": confidence,
        "inferred_by": f"llm-inference:{confidence:.3f}",
        "timestamp": "2026-05-18T12:00:00+00:00",
    }


def test_review_mismatch_records_event(tmp_path: Path) -> None:
    """When REVIEW flags a mis-specified slot that was previously
    common-ground at ≥0.95, an intent_miss event is recorded with the
    review-mismatch trigger."""
    audit = tmp_path / "silent-intent-miss.jsonl"
    event = record_intent_miss(
        "Database engine",
        trigger="review-mismatch",
        original_mark=_mark("Database engine"),
        notes="REVIEW round 2 flagged 'should-have-asked' on Database engine",
        audit_path=audit,
    )
    assert event.slot == "Database engine"
    assert event.trigger == "review-mismatch"
    assert event.original_mark_source == "LLM-inferred"
    assert event.original_mark_confidence == 0.97
    assert audit.exists()
    line = audit.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["slot"] == "Database engine"
    assert payload["trigger"] == "review-mismatch"


def test_session_reopen_records_event(tmp_path: Path) -> None:
    """User reopening a marked slot in-session also triggers the counter."""
    audit = tmp_path / "im.jsonl"
    event = record_intent_miss(
        "MQTT topic format",
        trigger="session-reopen",
        original_mark=_mark("MQTT topic format", source="LLM-inferred", confidence=0.98),
        audit_path=audit,
    )
    assert event.trigger == "session-reopen"
    assert event.original_mark_confidence == 0.98


def test_no_audit_path_returns_event_without_write() -> None:
    """audit_path=None still returns the event (in-memory logging path)."""
    event = record_intent_miss(
        "S",
        trigger="review-mismatch",
        original_mark=_mark("S"),
    )
    assert isinstance(event, IntentMissEvent)


def test_missing_original_mark_defaults_unknown() -> None:
    """When the original mark is None (defensive), source='unknown', conf=0.0."""
    event = record_intent_miss(
        "S",
        trigger="review-mismatch",
        original_mark=None,
    )
    assert event.original_mark_source == "unknown"
    assert event.original_mark_confidence == 0.0


def test_invalid_confidence_coerced_to_zero() -> None:
    """A malformed `confidence` in the original mark falls back to 0.0."""
    event = record_intent_miss(
        "S",
        trigger="review-mismatch",
        original_mark={"source": "X", "confidence": "not a float"},
    )
    assert event.original_mark_confidence == 0.0


def test_multiple_events_append_to_jsonl(tmp_path: Path) -> None:
    """Each call appends ONE line; the file is JSONL (one JSON object per line)."""
    audit = tmp_path / "im.jsonl"
    record_intent_miss("A", trigger="review-mismatch", original_mark=_mark("A"), audit_path=audit)
    record_intent_miss("B", trigger="session-reopen", original_mark=_mark("B"), audit_path=audit)
    lines = [line for line in audit.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    assert payloads[0]["slot"] == "A"
    assert payloads[1]["slot"] == "B"


def test_event_logged_with_provenance(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every recorded event also emits a WARNING log with provenance details
    so operators see signals even without reading the JSONL log."""
    import logging

    with caplog.at_level(logging.WARNING, logger="harness_maker.observability.intent_miss"):
        record_intent_miss(
            "Database engine",
            trigger="review-mismatch",
            original_mark=_mark("Database engine"),
        )
    assert any(
        "silent_intent_miss recorded" in r.message and "Database engine" in r.message
        for r in caplog.records
    )


def test_simulated_review_hook_contract(tmp_path: Path) -> None:
    """End-to-end: simulate REVIEW reading PLAN frontmatter common_ground_marks
    and calling record_intent_miss on a flagged mis-specification.

    This is the contract F8c's review.md.j2 hook embodies. The Python module
    proves the call shape; the actual template invokes it via the LLM at
    review time."""
    # Synthetic PLAN frontmatter (subset of ADR-009 schema)
    plan_frontmatter_marks = [
        _mark("Database engine", source="LLM-inferred", confidence=0.97),
        _mark("Auth scheme", source="CLAUDE.md", confidence=1.0),
    ]

    # Synthetic REVIEW agent output: flags "Database engine" as mis-spec.
    review_flagged_slots = ["Database engine"]

    audit = tmp_path / "im.jsonl"
    events_recorded: list[IntentMissEvent] = []
    for slot in review_flagged_slots:
        # Look up the original mark by slot name.
        original = next((m for m in plan_frontmatter_marks if m["slot"] == slot), None)
        if original is None:
            continue  # not common-ground — no intent-miss
        event = record_intent_miss(
            slot,
            trigger="review-mismatch",
            original_mark=original,
            notes=f"REVIEW flagged '{slot}' as under-specified",
            audit_path=audit,
        )
        events_recorded.append(event)

    assert len(events_recorded) == 1
    assert events_recorded[0].slot == "Database engine"
    assert events_recorded[0].original_mark_source == "LLM-inferred"
    # Audit log has exactly one entry.
    lines = audit.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
