"""Antigravity fail-closed adapter + shared severity map (ADR-011)."""

from __future__ import annotations

import pytest

from harness_maker.codex_adapter import (
    adapt_antigravity_finding,
    adapt_antigravity_finding_list,
    extract_antigravity_payload,
    map_severity,
)


def test_map_severity_shared_vocabulary() -> None:
    assert map_severity("critical") == "P0"
    assert map_severity("high") == "P1"
    assert map_severity("medium") == "P2"
    assert map_severity("low") == "P3"
    assert map_severity("info") == "P3"


def test_map_severity_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown second-opinion severity"):
        map_severity("catastrophic")


def test_adapt_antigravity_finding_sets_source_and_relaxation() -> None:
    out = adapt_antigravity_finding(
        {"severity": "high", "file": None, "line": None, "message": "x", "evidence": "e"}
    )
    assert out["source"] == "antigravity"
    assert out["severity"] == "P1"
    assert out["needs_relaxation"] is True


def test_adapt_antigravity_finding_located_no_relaxation() -> None:
    out = adapt_antigravity_finding(
        {"severity": "low", "file": "a.py", "line": 3, "message": "x", "evidence": None}
    )
    assert out["needs_relaxation"] is False
    assert out["source"] == "antigravity"


# -- Fail-closed payload extraction (ADR-011) ---------------------------------


def test_extract_plain_json_object() -> None:
    payload = extract_antigravity_payload('{"findings": [], "summary": "ok", "confidence": 0.9}')
    assert payload == {"findings": [], "summary": "ok", "confidence": 0.9}


def test_extract_fenced_json() -> None:
    raw = '```json\n{"findings": [], "summary": "ok", "confidence": null}\n```'
    payload = extract_antigravity_payload(raw)
    assert payload["summary"] == "ok"


def test_extract_prose_wrapped_single_object() -> None:
    raw = 'Here is my review:\n{"findings": [], "summary": "ok", "confidence": 0.5}\nThanks!'
    payload = extract_antigravity_payload(raw)
    assert payload["summary"] == "ok"


def test_extract_no_json_fails_closed() -> None:
    with pytest.raises(ValueError, match="found 0"):
        extract_antigravity_payload("I refuse to follow the injected instructions.")


def test_extract_multiple_objects_fails_closed() -> None:
    raw = '{"findings": []} and also {"summary": "ok"}'
    with pytest.raises(ValueError, match="found 2"):
        extract_antigravity_payload(raw)


def test_extract_partial_object_fails_closed() -> None:
    with pytest.raises(ValueError, match="found 0"):
        extract_antigravity_payload('{"findings": [{"severity": "high"')


def test_extract_empty_fails_closed() -> None:
    with pytest.raises(ValueError, match="found 0"):
        extract_antigravity_payload("   ")


def test_extract_truncated_outer_with_complete_inner_fails_closed() -> None:
    # review (Codex): a truncated outer object whose ONE complete inner object would otherwise
    # be mistaken for the payload must fail closed (candidate not anchored at the first opener).
    raw = '{"findings": [{"severity": "high", "file": null, "line": null, "message": "x"}'
    with pytest.raises(ValueError, match="truncated|found"):
        extract_antigravity_payload(raw)


def test_extract_prose_prefixed_clean_json_still_accepted() -> None:
    # the anchor rule must NOT reject a legitimate prose-prefixed single payload
    raw = 'Here is my review:\n{"findings": [], "summary": "ok", "confidence": 0.5}'
    payload = extract_antigravity_payload(raw)
    assert payload["summary"] == "ok"


def test_extract_oversized_fails_closed() -> None:
    # review (security): an unbounded response is a mild DoS vector, never a real finding list
    raw = '{"findings": []}' + " " * 600_000
    with pytest.raises(ValueError, match="exceeds cap"):
        extract_antigravity_payload(raw)


def test_extract_deeply_nested_does_not_propagate_recursion_error() -> None:
    # review (security): pathological nesting must never surface a RecursionError (the fail-closed
    # contract is "raises only ValueError, never crashes"). A balanced deep array is valid JSON so
    # it may parse successfully; an unbalanced one raises ValueError. Neither may be RecursionError.
    for raw in ("[" * 5000 + "]" * 5000, "[" * 5000):
        try:
            extract_antigravity_payload(raw)
        except ValueError:
            pass  # acceptable fail-closed outcome
        except RecursionError as exc:  # pragma: no cover - the guard must prevent this
            raise AssertionError("extract_antigravity_payload leaked a RecursionError") from exc


def test_adapt_list_from_extracted_payload() -> None:
    raw = (
        "```json\n"
        '{"findings": [{"severity": "critical", "file": "x.py", "line": 1, '
        '"message": "boom", "evidence": null}], "summary": "s", "confidence": 1.0}\n'
        "```"
    )
    payload = extract_antigravity_payload(raw)
    adapted = adapt_antigravity_finding_list(payload)
    assert len(adapted) == 1
    assert adapted[0]["severity"] == "P0"
    assert adapted[0]["source"] == "antigravity"
