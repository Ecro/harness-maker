"""Strict, side-effect-free parsing of Claude Code second-opinion responses.

Consumes the documented result/structured_output envelope. Transport, stage
selection, normalization, votes and ledger writes belong to later integration.
"""

import json
from typing import Any, Literal, NoReturn

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

DEFAULT_MAX_BYTES = 1024 * 1024


class ClaudeResponseError(ValueError):
    """Fixed diagnostic code without untrusted provider content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _Finding(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    severity: Literal["info", "low", "medium", "high", "critical"]
    message: str
    evidence: str | None
    file: str | None
    line: int | None

    @field_validator("line", mode="before")
    @classmethod
    def _schema_integer(cls, value: Any) -> Any:
        # JSON Schema accepts 3.0 as an integer; strict Python int does not.
        # Preserve strict rejection of booleans, strings and fractional values.
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    @field_validator("message")
    @classmethod
    def _nonblank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("empty finding")
        return value


class _Payload(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)

    findings: list[_Finding]
    summary: str
    confidence: float | None


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> NoReturn:
    raise ValueError("non-finite JSON number")


def parse_response(
    raw: bytes, *, returncode: int, max_bytes: int = DEFAULT_MAX_BYTES
) -> dict[str, Any]:
    """Return validated findings or a bounded, non-sensitive failure code.

    A successful process is necessary but insufficient. No text fallback is used:
    missing structured output is not a clean review. The payload follows the
    packaged finding schema, with an additional nonblank-message requirement.
    """
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    if returncode != 0:
        raise ClaudeResponseError("process_failed")
    if len(raw) > max_bytes:
        raise ClaudeResponseError("output_too_large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ClaudeResponseError("invalid_encoding") from None
    try:
        envelope = json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    except (ValueError, RecursionError):
        raise ClaudeResponseError("invalid_json") from None
    if not isinstance(envelope, dict) or envelope.get("type") != "result":
        raise ClaudeResponseError("invalid_envelope")
    if envelope.get("is_error") is True or str(envelope.get("subtype", "")).startswith("error"):
        raise ClaudeResponseError("provider_failed")
    if envelope.get("is_error") is not False or envelope.get("subtype") != "success":
        raise ClaudeResponseError("invalid_envelope")
    if "structured_output" not in envelope:
        raise ClaudeResponseError("missing_payload")
    try:
        return _Payload.model_validate(envelope["structured_output"]).model_dump()
    except ValidationError:
        raise ClaudeResponseError("invalid_payload") from None
