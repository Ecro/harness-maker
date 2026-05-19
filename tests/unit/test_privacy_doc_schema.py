"""Schema-drift defense: asserts every telemetry field is documented in PRIVACY.md (ADR-004)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIVACY_DOC = REPO_ROOT / "PRIVACY.md"

# (module_path_relative_to_repo, class_or_function_name, kind)
# kind = "model" → pydantic BaseModel / dataclass; we collect attribute names
# kind = "build_entry" → telemetry._build_entry; we collect entry["..."] keys
TELEMETRY_SOURCES: list[tuple[str, str, str]] = [
    ("src/harness_maker/telemetry.py", "OverrideRecord", "model"),
    ("src/harness_maker/telemetry.py", "_build_entry", "build_entry"),
    ("src/harness_maker/review_telemetry.py", "ReviewTelemetryRecord", "model"),
    ("src/harness_maker/observability/intent_miss.py", "IntentMissEvent", "model"),
]

# `model_config = ConfigDict(...)` on pydantic BaseModel uses a plain Assign,
# not AnnAssign — the collector below ignores it without needing a deny-list.
# Kept here as a guard in case a future annotated class-var slips through.
SCHEMA_INFRA_FIELDS: frozenset[str] = frozenset({"model_config"})


def _collect_model_fields(tree: ast.AST, class_name: str) -> set[str]:
    """Return the set of field names declared on a pydantic BaseModel or @dataclass.

    Field names come from class-body AnnAssign nodes (`name: Type` or
    `name: Type = default`). Helper functions / methods are ignored.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            fields: set[str] = set()
            for body_node in node.body:
                if isinstance(body_node, ast.AnnAssign) and isinstance(body_node.target, ast.Name):
                    fields.add(body_node.target.id)
            return fields - SCHEMA_INFRA_FIELDS
    raise LookupError(f"class {class_name!r} not found in AST")


def _collect_build_entry_keys(tree: ast.AST, func_name: str) -> set[str]:
    """Return every `entry["..."]` key assigned inside the named function."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            keys: set[str] = set()
            # Pick up `entry["k"] = v`
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Assign)
                    and len(child.targets) == 1
                    and isinstance(child.targets[0], ast.Subscript)
                    and isinstance(child.targets[0].value, ast.Name)
                    and child.targets[0].value.id == "entry"
                    and isinstance(child.targets[0].slice, ast.Constant)
                    and isinstance(child.targets[0].slice.value, str)
                ):
                    keys.add(child.targets[0].slice.value)
            # Pick up dict-literal initializer `entry: dict[...] = {"k": ...}`
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.AnnAssign)
                    and isinstance(child.target, ast.Name)
                    and child.target.id == "entry"
                    and isinstance(child.value, ast.Dict)
                ):
                    for k in child.value.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            keys.add(k.value)
            return keys
    raise LookupError(f"function {func_name!r} not found in AST")


def _collect_all_documented_field_names(doc_text: str) -> set[str]:
    """Extract every backticked identifier that appears in PRIVACY.md.

    The doc uses `` `name` `` to mark schema field names inside tables.
    We pull them all out and let the caller assert subset relationships.
    """
    return set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", doc_text))


@pytest.fixture(scope="module")
def documented_fields() -> set[str]:
    if not PRIVACY_DOC.exists():
        pytest.fail(
            f"PRIVACY.md not found at {PRIVACY_DOC}. "
            "If you removed it intentionally, also remove ADR-004 and this test."
        )
    return _collect_all_documented_field_names(PRIVACY_DOC.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("module_rel", "name", "kind"), TELEMETRY_SOURCES)
def test_privacy_doc_covers_telemetry_schema(
    documented_fields: set[str], module_rel: str, name: str, kind: str
) -> None:
    """Every field written to a telemetry JSONL must appear in PRIVACY.md."""
    src_path = REPO_ROOT / module_rel
    assert src_path.exists(), f"missing telemetry source: {src_path}"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))

    if kind == "model":
        emitted_fields = _collect_model_fields(tree, name)
    elif kind == "build_entry":
        emitted_fields = _collect_build_entry_keys(tree, name)
    else:
        pytest.fail(f"unknown kind {kind!r}")

    missing = emitted_fields - documented_fields
    assert not missing, (
        f"PRIVACY.md is missing {len(missing)} field(s) from {module_rel}::{name}: "
        f"{sorted(missing)}. Add them under the matching schema section."
    )


def test_privacy_doc_lists_all_four_jsonl_paths() -> None:
    """ADR-004 promises four JSONL files. Each path pattern must be named."""
    if not PRIVACY_DOC.exists():
        pytest.fail(f"PRIVACY.md not found at {PRIVACY_DOC}")
    text = PRIVACY_DOC.read_text(encoding="utf-8")
    expected_path_substrings = [
        "metrics-",  # metrics-{YYYY-MM-DD}.jsonl
        "overrides.jsonl",
        "review-",  # review-{YYYY-MM-DD}.jsonl
        "silent-intent-miss-",
    ]
    missing = [p for p in expected_path_substrings if p not in text]
    assert not missing, f"PRIVACY.md does not mention these JSONL paths: {missing}"
