"""Common-ground detection for the 5-term inequality gate (0.16.0).

Per PLAN-deep-interview-question-criteria:
- ADR-003: explicit-evidence sources PLUS optional LLM-inference at confidence >= 0.95
- ADR-009: two write sinks (in-process accumulator for PLAN frontmatter +
  append-only JSONL audit at .claude/observability/cg-marks-{slug}.jsonl)
- ADR-012: kill-switch `llm_inference_enabled` (default True) skips inference path

The gate filters out interview candidate slots whose answer is already
determined ("don't ask the obvious") before EIG ranking.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ADR-003: threshold for LLM-inference path to emit a mark.
DEFAULT_LLM_INFERENCE_THRESHOLD = 0.95

# Append-only JSONL line size safety margin. The PIPE_BUF atomicity
# guarantee applies to pipes/FIFOs, NOT regular files; for `path.open("a")`
# POSIX provides no equivalent contract. In our single-process audit-log
# use case this is harmless, but we still warn for oversized lines so
# operators investigating concurrent-writer scenarios have a signal.
_JSONL_LINE_SAFETY_MARGIN_BYTES = 4000


@dataclass(frozen=True)
class CGMark:
    """A single common-ground mark with provenance.

    Persisted both to the caller's in-process accumulator (for PLAN frontmatter
    write at interview close) AND to a slug-scoped JSONL audit log
    `.claude/observability/cg-marks-{slug}.jsonl` for /hm:health drift analysis.

    ADR-009 schema:
      source       — one of the literals enumerated in `KNOWN_SOURCES`, OR
                     "prior-answer:{round_n}" / "LLM-inferred:{model}"
      inferred_by  — "explicit" | "llm-inference:{confidence:.3f}"
      confidence   — 0.0-1.0; 1.0 for explicit, [threshold, 1.0] for LLM
      timestamp    — ISO 8601 UTC, second precision
    """

    slot: str
    source: str
    confidence: float
    inferred_by: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ADR-009 enumerated source labels (the static set; dynamic suffixes use prefix match).
KNOWN_SOURCES: frozenset[str] = frozenset(
    {
        "CLAUDE.md",
        "harness.yaml",
        "SPEC-frontmatter",
        "RESEARCH-frontmatter",
        "PLAN-history",
        "REVIEW-history",
    }
)


# LLM-inference path callable contract (mocked in tests).
# Signature: (slot, context) -> confidence in [0.0, 1.0]. Real implementation
# lives in F6 (interview integration); F2 ships the injection point only.
LLMInferenceFn = Callable[[str, dict[str, Any]], float]


def detect_common_ground(
    slot: str,
    sources: dict[str, Any],
    *,
    llm_inference_enabled: bool = True,
    llm_inference_threshold: float = DEFAULT_LLM_INFERENCE_THRESHOLD,
    llm_inference_fn: LLMInferenceFn | None = None,
    audit_path: Path | None = None,
    accumulator: list[CGMark] | None = None,
) -> CGMark | None:
    """Detect if `slot` is common-ground (already determined → skip asking).

    Returns a CGMark when detected (and appends to accumulator + JSONL audit
    when provided); None when the slot is NOT common-ground (interview must ask).

    The function checks explicit-evidence sources first; only if no explicit
    match is found AND `llm_inference_enabled` is True does it consult
    `llm_inference_fn`. The ADR-012 kill-switch (default True) skips the
    LLM path when False — i.e., reverts ADR-003 to minimal explicit-only mode.

    Args:
      slot: The interview slot name being checked (e.g. "Database engine").
      sources: Mapping of `source_label → content`. Labels SHOULD match
        the ADR-009 schema (`KNOWN_SOURCES`) plus dynamic suffix forms
        `prior-answer:{round_n}` / `LLM-inferred:{model}`; unknown labels
        are still scanned but tagged "unknown-source:{label}" if a hit.
      llm_inference_enabled: ADR-012 kill-switch. False = explicit-only.
      llm_inference_threshold: ADR-003 cutoff (default 0.95). Inclusive.
      llm_inference_fn: Mock-able callable; real implementation lives in F6.
      audit_path: When provided, marks are appended (atomic line-write).
      accumulator: When provided, marks are appended in-process.
    """
    explicit = _check_explicit_sources(slot, sources)
    if explicit is not None:
        _persist(explicit, audit_path, accumulator)
        return explicit

    if llm_inference_enabled and llm_inference_fn is not None:
        try:
            confidence = float(llm_inference_fn(slot, sources))
        except (TypeError, ValueError) as exc:
            logger.warning(
                "common_ground LLM-inference returned non-numeric for slot %r "
                "— treated as 0.0 (%s)",
                slot,
                exc,
            )
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        if confidence >= llm_inference_threshold:
            mark = CGMark(
                slot=slot,
                source="LLM-inferred",
                confidence=confidence,
                inferred_by=f"llm-inference:{confidence:.3f}",
                timestamp=_now_iso(),
            )
            _persist(mark, audit_path, accumulator)
            return mark

    return None


def _check_explicit_sources(slot: str, sources: dict[str, Any]) -> CGMark | None:
    """Conservative explicit-evidence matcher.

    Why conservative: a free-form substring match against CLAUDE.md prose
    (e.g. "use any database engine you prefer") would over-trigger and
    mask user intent — the very silent-miss failure mode ADR-008 monitors.
    So we only treat a slot as explicitly determined when source content
    references it as a STRUCTURED FIELD or HEADING. Fuzzy semantic matches
    fall through to the LLM-inference path (and its 0.95 threshold).

    Match rules per source content type:
      dict / list      → check `slot` as key (case-insensitive, deep walk).
      str (yaml-ish)   → `^slot:` line (anchored) OR `# slot` heading.
      anything else    → skip.
    """
    pattern_key = re.compile(rf"^\s*{re.escape(slot)}\s*:", re.IGNORECASE | re.MULTILINE)
    pattern_heading = re.compile(rf"^#+\s+{re.escape(slot)}\s*$", re.IGNORECASE | re.MULTILINE)
    for source_label, content in sources.items():
        if content is None:
            continue
        if _matches_structured(slot, content, pattern_key, pattern_heading):
            label = (
                source_label if _is_known_source(source_label) else f"unknown-source:{source_label}"
            )
            return CGMark(
                slot=slot,
                source=label,
                confidence=1.0,
                inferred_by="explicit",
                timestamp=_now_iso(),
            )
    return None


def _is_known_source(label: str) -> bool:
    """ADR-009 source label validity check."""
    if label in KNOWN_SOURCES:
        return True
    return label.startswith("prior-answer:") or label.startswith("LLM-inferred:")


def _matches_structured(
    slot: str,
    content: Any,
    pattern_key: re.Pattern[str],
    pattern_heading: re.Pattern[str],
) -> bool:
    """Walk content for structured slot references."""
    if isinstance(content, dict):
        return _dict_has_key_ci(content, slot)
    if isinstance(content, list):
        return any(
            _matches_structured(slot, item, pattern_key, pattern_heading) for item in content
        )
    if isinstance(content, str):
        if pattern_key.search(content) is not None:
            return True
        if pattern_heading.search(content) is not None:
            return True
    return False


def _dict_has_key_ci(d: dict[Any, Any], slot: str) -> bool:
    slot_lower = slot.lower()
    for k, v in d.items():
        if isinstance(k, str) and k.lower() == slot_lower:
            return True
        if isinstance(v, (dict, list)):
            if isinstance(v, dict) and _dict_has_key_ci(v, slot):
                return True
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and _dict_has_key_ci(item, slot):
                        return True
    return False


def _now_iso() -> str:
    """ISO 8601 UTC second-precision timestamp."""
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _persist(
    mark: CGMark,
    audit_path: Path | None,
    accumulator: list[CGMark] | None,
) -> None:
    if accumulator is not None:
        accumulator.append(mark)
    if audit_path is not None:
        _append_jsonl(audit_path, mark)


def _append_jsonl(path: Path, mark: CGMark) -> None:
    """Append a single JSON line to the audit log.

    CLAUDE.md §atomic_write covers full-file rewrites via tempfile+os.rename;
    JSONL is append-only. POSIX guarantees write() atomicity for sizes <= PIPE_BUF
    when the file is opened O_APPEND. Lines beyond `_JSONL_LINE_SAFETY_MARGIN_BYTES`
    trigger a warning — concurrent appenders would risk torn writes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(mark.to_dict(), ensure_ascii=False)
    if len(line.encode("utf-8")) >= _JSONL_LINE_SAFETY_MARGIN_BYTES:
        logger.warning(
            "common_ground audit line for slot %r exceeds size safety margin (%d bytes); "
            "concurrent-writer scenarios may see torn writes",
            mark.slot,
            len(line),
        )
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
