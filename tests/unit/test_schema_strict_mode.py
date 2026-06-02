"""Strict-mode validity invariant for rendered JSON schemas (codex --output-schema)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

_SCHEMAS_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates" / "schemas"
)

# Keywords OpenAI/Codex strict structured-output mode rejects (or silently
# ignores) on several versions. Optionality is expressed as a nullable union
# type, never as a numeric/length/pattern constraint. PLAN ADR-001 dropped
# minimum/maximum/minLength specifically; the rest are pre-emptive (also
# non-strict-safe) so the guard stays correct if a future schema adds them.
_BANNED_CONSTRAINT_KEYWORDS = frozenset(
    {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minItems",
        "maxItems",
    }
)


def _iter_subschemas(node: dict[str, Any]) -> Any:
    """Yield every subschema reachable from ``node``, structurally.

    Recurses through ``properties`` *values*, ``items``, the composition arrays
    (``anyOf``/``allOf``/``oneOf``), and a schema-valued ``additionalProperties``
    — but NEVER treats a property *name* as a schema node. Walking the raw dict
    tree instead would scan the ``properties`` map itself, so a field literally
    named ``pattern``/``format``/``minimum`` would false-positive the
    banned-keyword check.
    """
    yield node
    props = node.get("properties")
    if isinstance(props, dict):
        for sub in props.values():
            if isinstance(sub, dict):
                yield from _iter_subschemas(sub)
    items = node.get("items")
    if isinstance(items, dict):
        yield from _iter_subschemas(items)
    elif isinstance(items, list):
        for sub in items:
            if isinstance(sub, dict):
                yield from _iter_subschemas(sub)
    for combinator in ("anyOf", "allOf", "oneOf"):
        arr = node.get(combinator)
        if isinstance(arr, list):
            for sub in arr:
                if isinstance(sub, dict):
                    yield from _iter_subschemas(sub)
    extra = node.get("additionalProperties")
    if isinstance(extra, dict):
        yield from _iter_subschemas(extra)


def strict_mode_violations(schema: dict[str, Any]) -> list[str]:
    """Return strict-mode contract violations for a JSON schema.

    Strict structured-output mode (`codex exec --output-schema`) requires that
    every object set ``additionalProperties: false`` AND list every key of its
    ``properties`` in ``required`` (optionality is encoded as a nullable union,
    not omission), and it rejects range/length/pattern constraint keywords.
    This is the exact invariant whose absence shipped the 0.28.6
    ``invalid_json_schema`` bug.

    Does not follow ``$ref`` — the rendered schemas under templates/schemas are
    self-contained (no ``$defs``); revisit if that changes.
    """
    violations: list[str] = []
    for node in _iter_subschemas(schema):
        for keyword in _BANNED_CONSTRAINT_KEYWORDS:
            if keyword in node:
                violations.append(f"banned constraint keyword present: {keyword}")
        props = node.get("properties")
        if isinstance(props, dict):
            if node.get("additionalProperties") is not False:
                violations.append("object with properties missing additionalProperties:false")
            required = node.get("required", [])
            missing = [key for key in props if key not in required]
            if missing:
                violations.append(f"properties not in required: {sorted(missing)}")
    return violations


def _schema_files() -> list[Path]:
    return sorted(_SCHEMAS_DIR.glob("*.json"))


def test_schemas_dir_has_at_least_one_schema() -> None:
    assert _schema_files(), f"no schema files under {_SCHEMAS_DIR}"


@pytest.mark.parametrize("schema_path", _schema_files(), ids=lambda p: p.name)
def test_rendered_schema_satisfies_strict_mode(schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    violations = strict_mode_violations(schema)
    assert not violations, f"{schema_path.name}: {violations}"


# Negative fixture — the EXACT pre-fix codex-finding shape. Committed so the
# RED-proof (this invariant catches the bug class) is permanent and re-runnable,
# rather than an ephemeral pre-fix checkout (PLAN ADR-002 / validator W4).
_KNOWN_BAD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["findings", "summary"],  # confidence omitted -> violation
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "message"],  # file/line/evidence omitted
                "properties": {
                    "severity": {"type": "string"},
                    "message": {"type": "string", "minLength": 1},  # banned keyword
                    "evidence": {"type": "string"},
                    "file": {"type": "string"},
                    "line": {"type": "integer", "minimum": 1},  # banned keyword
                },
            },
        },
        "summary": {"type": "string", "minLength": 1},  # banned keyword
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},  # banned keywords
    },
}


def test_validator_rejects_known_bad_schema() -> None:
    violations = strict_mode_violations(_KNOWN_BAD_SCHEMA)
    assert any("not in required" in v for v in violations), violations
    assert any("banned constraint keyword" in v for v in violations), violations


def test_property_named_like_a_keyword_is_not_a_false_positive() -> None:
    """A field literally named ``pattern`` must NOT trip the banned-keyword scan."""
    schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["pattern", "format"],
        "properties": {
            "pattern": {"type": "string"},
            "format": {"type": "string"},
        },
    }
    assert strict_mode_violations(schema) == []


def test_object_missing_additional_properties_false_is_flagged() -> None:
    """Strict mode requires additionalProperties:false on every object."""
    schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["inner"],
        "properties": {
            # nested object forgets additionalProperties:false
            "inner": {
                "type": "object",
                "required": ["x"],
                "properties": {"x": {"type": "string"}},
            },
        },
    }
    violations = strict_mode_violations(schema)
    assert any("missing additionalProperties:false" in v for v in violations), violations
