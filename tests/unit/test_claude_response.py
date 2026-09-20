"""Claude envelope examples follow the documented structured_output boundary."""

import json

import pytest

from harness_maker.claude_response import ClaudeResponseError, parse_response


def envelope(payload: object) -> bytes:
    return json.dumps(
        {"type": "result", "subtype": "success", "is_error": False, "structured_output": payload},
        ensure_ascii=False,
    ).encode()


def clean() -> dict[str, object]:
    return {"findings": [], "summary": "No findings", "confidence": 0.8}


def test_s4_valid_empty_opinion() -> None:
    assert parse_response(envelope(clean()), returncode=0) == clean()


def test_s4_finding_fields_are_preserved() -> None:
    payload = {
        "findings": [
            {
                "severity": "high",
                "message": "Missing guard",
                "evidence": "Input reaches writer",
                "file": "src/a.py",
                "line": 3,
            }
        ],
        "summary": "One finding",
        "confidence": None,
    }
    assert parse_response(envelope(payload), returncode=0) == payload


@pytest.mark.parametrize("line", [3.0, -2.0, 0.0])
def test_s4_schema_integer_allows_zero_fraction(line: float) -> None:
    # JSON Schema integer is mathematical, not the Python decoder's int type:
    # https://json-schema.org/understanding-json-schema/reference/numeric
    payload = {
        "findings": [
            {
                "severity": "info",
                "message": "Location",
                "evidence": None,
                "file": "a.py",
                "line": line,
            }
        ],
        "summary": "x",
        "confidence": None,
    }
    assert parse_response(envelope(payload), returncode=0) == payload


@pytest.mark.parametrize(
    ("markers", "code"),
    [
        ({"subtype": "success"}, "invalid_envelope"),
        ({"subtype": "success", "is_error": True}, "provider_failed"),
        ({"subtype": "error_max_turns", "is_error": False}, "provider_failed"),
        ({"is_error": False}, "invalid_envelope"),
        ({"subtype": "unknown", "is_error": False}, "invalid_envelope"),
        ({"subtype": "success", "is_error": 0}, "invalid_envelope"),
    ],
)
def test_s5_success_markers_are_independently_required(
    markers: dict[str, object], code: str
) -> None:
    raw = json.dumps({"type": "result", "structured_output": clean(), **markers}).encode()
    with pytest.raises(ClaudeResponseError) as exc:
        parse_response(raw, returncode=0)
    assert exc.value.code == code


@pytest.mark.parametrize(
    ("raw", "returncode", "code"),
    [
        (envelope(clean()), 1, "process_failed"),
        (b"not json", 0, "invalid_json"),
        (b"\xff", 0, "invalid_encoding"),
        (b"[]", 0, "invalid_envelope"),
        (b'{"type":"result","subtype":"error_max_turns","is_error":true}', 0, "provider_failed"),
        (
            b'{"type":"result","subtype":"success","is_error":false,"result":"No findings"}',
            0,
            "missing_payload",
        ),
        (b'{"is_error":true,"is_error":false}', 0, "invalid_json"),
        (
            envelope({"findings": [], "summary": "ok", "confidence": float("nan")}),
            0,
            "invalid_json",
        ),
        (envelope({"findings": []}), 0, "invalid_payload"),
    ],
)
def test_s5_failures_never_become_clean_opinions(raw: bytes, returncode: int, code: str) -> None:
    with pytest.raises(ClaudeResponseError) as exc:
        parse_response(raw, returncode=returncode)
    assert exc.value.code == code


@pytest.mark.parametrize(
    ("field", "value"),
    [("severity", "P1"), ("message", " "), ("line", True), ("line", 3.5), ("line", "3")],
)
def test_s5_invalid_finding_types_are_rejected(field: str, value: object) -> None:
    finding: dict[str, object] = {
        "severity": "high",
        "message": "Problem",
        "evidence": None,
        "file": None,
        "line": None,
    }
    finding[field] = value
    with pytest.raises(ClaudeResponseError, match="invalid_payload"):
        parse_response(
            envelope({"findings": [finding], "summary": "x", "confidence": None}), returncode=0
        )


def test_s6_size_limit_counts_bytes_and_does_not_echo_input() -> None:
    raw = envelope({"findings": [], "summary": "secret-한글", "confidence": None})
    assert parse_response(raw, returncode=0, max_bytes=len(raw))["findings"] == []
    with pytest.raises(ClaudeResponseError) as exc:
        parse_response(raw, returncode=0, max_bytes=len(raw.decode("utf-8")))
    assert exc.value.code == "output_too_large"
    assert "secret" not in str(exc.value)
