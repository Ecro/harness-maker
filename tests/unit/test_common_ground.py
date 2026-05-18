"""Unit tests for common_ground.detect_common_ground (PLAN F2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_maker.common_ground import (
    DEFAULT_LLM_INFERENCE_THRESHOLD,
    KNOWN_SOURCES,
    CGMark,
    detect_common_ground,
)

# ---------- Explicit-evidence path -----------------------------------------------------


def test_explicit_from_harness_yaml_dict() -> None:
    """A dict source with `slot` as a key triggers explicit common-ground."""
    sources: dict[str, Any] = {
        "harness.yaml": {"locale": "en", "Database engine": "postgres"},
    }
    mark = detect_common_ground("Database engine", sources)
    assert mark is not None
    assert mark.source == "harness.yaml"
    assert mark.confidence == 1.0
    assert mark.inferred_by == "explicit"


def test_explicit_from_yaml_string_key_line() -> None:
    """A string source with `^slot:` line matches structured (not free-form)."""
    sources: dict[str, Any] = {
        "harness.yaml": "preset: Production\nlocale: en\nDatabase engine: postgres\n",
    }
    mark = detect_common_ground("Database engine", sources)
    assert mark is not None
    assert mark.confidence == 1.0


def test_explicit_from_markdown_heading() -> None:
    """A markdown heading `# Slot` matches structured."""
    sources: dict[str, Any] = {
        "CLAUDE.md": "# Project conventions\n\n## Database engine\n\nWe use postgres.\n",
    }
    mark = detect_common_ground("Database engine", sources)
    assert mark is not None
    assert mark.source == "CLAUDE.md"


def test_explicit_match_case_insensitive() -> None:
    """Slot matching is case-insensitive against keys and headings."""
    sources: dict[str, Any] = {"harness.yaml": {"DATABASE ENGINE": "postgres"}}
    assert detect_common_ground("database engine", sources) is not None


def test_explicit_no_match_returns_none() -> None:
    """When no source has the slot as a structured field, return None."""
    sources: dict[str, Any] = {
        "CLAUDE.md": "# Project conventions\n\nWe value safety.\n",
        "harness.yaml": {"locale": "en"},
    }
    assert detect_common_ground("MQTT topic format", sources) is None


def test_freeform_prose_does_not_match() -> None:
    """Free-form prose mentioning the slot does NOT trigger explicit match.

    This is the conservative-matcher guard against silent-intent-miss
    (ADR-008 primary failure mode): "use any database engine you prefer"
    must NOT count as the user having chosen one.
    """
    sources: dict[str, Any] = {
        "CLAUDE.md": "Use any database engine you prefer; we're flexible.\n",
    }
    assert detect_common_ground("Database engine", sources) is None


def test_unknown_source_label_tagged() -> None:
    """An unknown source label is tagged with `unknown-source:` prefix when matched."""
    sources: dict[str, Any] = {"weird-source": {"Database engine": "postgres"}}
    mark = detect_common_ground("Database engine", sources)
    assert mark is not None
    assert mark.source == "unknown-source:weird-source"


def test_known_source_labels_set_complete() -> None:
    """ADR-009 enumerated sources are exactly the documented set."""
    expected = {
        "CLAUDE.md",
        "harness.yaml",
        "SPEC-frontmatter",
        "RESEARCH-frontmatter",
        "PLAN-history",
        "REVIEW-history",
    }
    assert expected == KNOWN_SOURCES


# ---------- LLM-inference path ---------------------------------------------------------


def test_llm_inference_above_threshold_emits_mark() -> None:
    """Self-reported confidence >= 0.95 emits a mark (default threshold)."""

    def mock_llm(slot: str, ctx: dict[str, Any]) -> float:
        return 0.97

    mark = detect_common_ground(
        "Some slot",
        {"CLAUDE.md": "unrelated content"},
        llm_inference_fn=mock_llm,
    )
    assert mark is not None
    assert mark.source == "LLM-inferred"
    assert mark.confidence == 0.97
    assert mark.inferred_by == "llm-inference:0.970"


def test_llm_inference_below_threshold_returns_none() -> None:
    """Confidence below 0.95 does NOT emit a mark — interview asks the slot."""

    def mock_llm(slot: str, ctx: dict[str, Any]) -> float:
        return 0.94

    assert (
        detect_common_ground(
            "Some slot",
            {"CLAUDE.md": "unrelated content"},
            llm_inference_fn=mock_llm,
        )
        is None
    )


def test_llm_inference_at_exact_threshold_emits_mark() -> None:
    """Boundary: exactly 0.95 is inclusive (>=)."""

    def mock_llm(slot: str, ctx: dict[str, Any]) -> float:
        return 0.95

    mark = detect_common_ground(
        "Some slot",
        {"CLAUDE.md": "unrelated"},
        llm_inference_fn=mock_llm,
    )
    assert mark is not None
    assert mark.confidence == 0.95


def test_kill_switch_skips_llm_path() -> None:
    """ADR-012 kill-switch: llm_inference_enabled=False bypasses inference entirely."""

    def mock_llm(slot: str, ctx: dict[str, Any]) -> float:
        return 1.0  # would otherwise trigger

    assert (
        detect_common_ground(
            "Some slot",
            {"CLAUDE.md": "unrelated"},
            llm_inference_enabled=False,
            llm_inference_fn=mock_llm,
        )
        is None
    )


def test_no_llm_fn_skips_llm_path() -> None:
    """When no llm_inference_fn is supplied, only explicit-evidence counts."""
    assert (
        detect_common_ground(
            "Database engine",
            {"CLAUDE.md": "unrelated"},
            llm_inference_enabled=True,
            llm_inference_fn=None,
        )
        is None
    )


def test_llm_invalid_return_treated_as_zero() -> None:
    """Non-numeric mock return is treated as 0.0 confidence (defensive)."""

    def mock_llm(slot: str, ctx: dict[str, Any]) -> float:
        return "not a number"  # type: ignore[return-value]

    assert (
        detect_common_ground(
            "Some slot",
            {"CLAUDE.md": "unrelated"},
            llm_inference_fn=mock_llm,
        )
        is None
    )


def test_llm_confidence_clamped_to_unit_interval() -> None:
    """LLM returning >1.0 or <0.0 is clamped, not raised."""

    def mock_high(slot: str, ctx: dict[str, Any]) -> float:
        return 1.5

    mark = detect_common_ground("S", {"CLAUDE.md": "x"}, llm_inference_fn=mock_high)
    assert mark is not None
    assert mark.confidence == 1.0


def test_custom_threshold_respected() -> None:
    """User-set threshold via llm_inference_threshold arg overrides default."""

    def mock_llm(slot: str, ctx: dict[str, Any]) -> float:
        return 0.81

    assert (
        detect_common_ground(
            "S",
            {"CLAUDE.md": "x"},
            llm_inference_fn=mock_llm,
            llm_inference_threshold=0.80,
        )
        is not None
    )


def test_default_threshold_is_0_95() -> None:
    """Sentinel: DEFAULT_LLM_INFERENCE_THRESHOLD matches ADR-003."""
    assert DEFAULT_LLM_INFERENCE_THRESHOLD == 0.95


# ---------- Explicit beats LLM (precedence) --------------------------------------------


def test_explicit_short_circuits_llm() -> None:
    """When explicit-evidence matches, LLM-inference fn is NOT called."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def mock_llm(slot: str, ctx: dict[str, Any]) -> float:
        calls.append((slot, ctx))
        return 1.0

    sources: dict[str, Any] = {"harness.yaml": {"Database engine": "postgres"}}
    mark = detect_common_ground(
        "Database engine",
        sources,
        llm_inference_fn=mock_llm,
    )
    assert mark is not None
    assert mark.inferred_by == "explicit"
    assert calls == [], "LLM should NOT be called when explicit match exists"


# ---------- Persistence: accumulator + JSONL audit -------------------------------------


def test_accumulator_collects_marks() -> None:
    """Caller-supplied accumulator receives detected marks."""
    accum: list[CGMark] = []
    sources: dict[str, Any] = {"harness.yaml": {"Database engine": "postgres"}}
    detect_common_ground("Database engine", sources, accumulator=accum)
    assert len(accum) == 1
    assert accum[0].slot == "Database engine"


def test_accumulator_unchanged_on_no_match() -> None:
    """Accumulator stays empty when slot is not common-ground."""
    accum: list[CGMark] = []
    detect_common_ground(
        "MQTT topic format", {"CLAUDE.md": "no relevant content"}, accumulator=accum
    )
    assert accum == []


def test_jsonl_audit_appends_one_line_per_detection(tmp_path: Path) -> None:
    """Audit log gains exactly one JSON line per detected mark."""
    audit = tmp_path / "cg-marks-test.jsonl"
    sources: dict[str, Any] = {"harness.yaml": {"Database engine": "postgres"}}

    detect_common_ground("Database engine", sources, audit_path=audit)
    detect_common_ground(
        "Database engine", sources, audit_path=audit
    )  # second call: same slot, separate line

    text = audit.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    for payload in payloads:
        assert payload["slot"] == "Database engine"
        assert payload["source"] == "harness.yaml"
        assert payload["confidence"] == 1.0


def test_jsonl_audit_parent_dir_created(tmp_path: Path) -> None:
    """Audit writer creates the .claude/observability/ parent path on demand."""
    audit = tmp_path / "deep" / "nested" / "cg.jsonl"
    sources: dict[str, Any] = {"harness.yaml": {"Database engine": "x"}}
    detect_common_ground("Database engine", sources, audit_path=audit)
    assert audit.exists()
    assert audit.parent.is_dir()


def test_jsonl_audit_no_write_on_no_match(tmp_path: Path) -> None:
    """No detection → no audit line written. _append_jsonl is short-circuited
    in detect_common_ground when no mark is produced, so the audit file is
    never created."""
    audit = tmp_path / "cg.jsonl"
    detect_common_ground("MQTT", {"CLAUDE.md": "x"}, audit_path=audit)
    assert not audit.exists(), "audit file must not be created on no-match path"


def test_cgmark_to_dict_roundtrip() -> None:
    """CGMark.to_dict produces JSON-serializable payload preserving all fields."""
    mark = CGMark(
        slot="Test",
        source="CLAUDE.md",
        confidence=0.97,
        inferred_by="llm-inference:0.970",
        timestamp="2026-05-18T12:00:00+00:00",
    )
    payload = mark.to_dict()
    serialized = json.dumps(payload)
    loaded = json.loads(serialized)
    assert loaded == payload
