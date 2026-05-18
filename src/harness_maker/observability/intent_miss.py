"""Silent-intent-miss telemetry (ADR-008)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from harness_maker.io_utils import atomic_append

logger = logging.getLogger(__name__)

# Closed union per ADR-008 §triggers. Add new triggers explicitly (mypy --strict
# will reject string literals not in this set). Currently no plans for
# "wrapup-reopen" — wrapup does not currently re-visit slot decisions; if that
# changes, extend this Literal AND update record_intent_miss callers.
Trigger = Literal["review-mismatch", "session-reopen"]


@dataclass(frozen=True)
class IntentMissEvent:
    """A single silent-intent-miss event.

    ADR-003 chose aggressive LLM-inference for common-ground (≥0.95 confidence).
    When that inference is wrong, this event captures the post-hoc signal
    (REVIEW flagged the slot as mis-specified, OR user reopened the slot)
    so `/hm:health` can surface drift and operators can re-calibrate.
    """

    slot: str
    trigger: Trigger
    original_mark_source: str
    original_mark_confidence: float
    detected_at: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def record_intent_miss(
    slot: str,
    *,
    trigger: Trigger,
    original_mark: dict[str, Any] | None,
    notes: str = "",
    audit_path: Path | None = None,
) -> IntentMissEvent:
    """Record a silent-intent-miss event for ADR-008 telemetry.

    Two trigger paths:
      - "review-mismatch": REVIEW stage flagged this slot as mis-specified,
        even though it was previously marked common-ground. The aggressive
        ADR-003 inference was wrong; user paid the cost.
      - "session-reopen": User explicitly reopened this slot in the same
        interview session after it was marked common-ground.

    The event is logged (always) AND appended to the JSONL audit log when
    `audit_path` is provided. `/hm:health` reads the audit log to compute
    silent_intent_miss_rate.

    No-raise contract: this function never raises. JSON line errors are
    swallowed; type-coercion fallbacks produce a valid event. Callers must
    not treat the return value as a success/failure signal.
    """
    src = original_mark.get("source", "unknown") if original_mark else "unknown"
    try:
        conf = float(original_mark.get("confidence", 0.0)) if original_mark else 0.0
    except (TypeError, ValueError):
        conf = 0.0
    event = IntentMissEvent(
        slot=slot,
        trigger=trigger,
        original_mark_source=str(src),
        original_mark_confidence=conf,
        detected_at=_now_iso(),
        notes=notes,
    )
    logger.warning(
        "ADR-008 silent_intent_miss recorded: slot=%r trigger=%s "
        "original_source=%s original_confidence=%.3f",
        slot,
        trigger,
        src,
        conf,
    )
    if audit_path is not None:
        _append_jsonl(audit_path, event)
    return event


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _append_jsonl(path: Path, event: IntentMissEvent) -> None:
    """Append the event as one JSONL line via the codebase-standard
    atomic_append helper (single os.write on O_APPEND fd — POSIX guarantees
    atomicity ≤ PIPE_BUF for concurrent appenders)."""
    line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"
    if len(line.encode("utf-8")) >= 4000:
        logger.warning(
            "intent_miss audit line for slot %r exceeds 4000-byte safety "
            "margin; POSIX atomic-append guarantee may not hold",
            event.slot,
        )
    atomic_append(path, line)
