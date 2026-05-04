"""Rubric YAML loader — multi-doc parsing + schema validation."""

from __future__ import annotations

from pathlib import Path

from harness_maker.rubric_loader import (
    Rubric,
    RubricFile,
    load_rubric_file,
    load_rubrics,
)

_VALID_RUBRIC_DOC = """\
---
generated_by: harness-maker
content_hash: abc123
---
dimension: context_quality
target: CLAUDE.md
rubrics:
  - id: stack_specified
    description: Does the file mention tech stack?
    severity: P0
    action: Add a Tech Stack section.
  - id: lint_documented
    description: Are lint commands documented?
    severity: P1
    action: Document lint commands.
"""


def test_load_valid_rubric_file(tmp_path: Path) -> None:
    p = tmp_path / "claude_md.yaml"
    p.write_text(_VALID_RUBRIC_DOC, encoding="utf-8")
    rf = load_rubric_file(p)
    assert isinstance(rf, RubricFile)
    assert rf.dimension == "context_quality"
    assert rf.target == "CLAUDE.md"
    assert len(rf.rubrics) == 2
    assert rf.rubrics[0].id == "stack_specified"
    assert rf.rubrics[0].severity == "P0"


def test_load_missing_file(tmp_path: Path) -> None:
    assert load_rubric_file(tmp_path / "missing.yaml") is None


def test_load_malformed_yaml(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("not: valid\n  yaml: [\n", encoding="utf-8")
    assert load_rubric_file(p) is None


def test_load_yaml_without_rubrics_key(tmp_path: Path) -> None:
    p = tmp_path / "irrelevant.yaml"
    p.write_text("foo: bar\nbaz: qux\n", encoding="utf-8")
    assert load_rubric_file(p) is None


def test_load_yaml_with_invalid_severity_passes_validation(tmp_path: Path) -> None:
    """Severity is a free-text string per schema; we don't enforce values here."""
    p = tmp_path / "weird.yaml"
    p.write_text(
        """
dimension: context_quality
target: CLAUDE.md
rubrics:
  - id: foo
    description: foo
    severity: critical
    action: fix it
""",
        encoding="utf-8",
    )
    rf = load_rubric_file(p)
    assert rf is not None
    assert rf.rubrics[0].severity == "critical"


def test_load_yaml_with_extra_field_rejected(tmp_path: Path) -> None:
    """extra='forbid' means stray fields fail validation."""
    p = tmp_path / "extra.yaml"
    p.write_text(
        """
dimension: context_quality
target: CLAUDE.md
extra_top_field: oops
rubrics:
  - id: x
    description: x
    severity: P0
    action: x
""",
        encoding="utf-8",
    )
    assert load_rubric_file(p) is None


def test_load_rubrics_directory(tmp_path: Path) -> None:
    (tmp_path / "claude_md.yaml").write_text(_VALID_RUBRIC_DOC, encoding="utf-8")
    (tmp_path / "agent_prompt.yaml").write_text(
        """
dimension: context_quality
target: .claude/agents/*.md
rubrics:
  - id: contract_format
    description: contract format used?
    severity: P1
    action: restructure
""",
        encoding="utf-8",
    )
    (tmp_path / "irrelevant.yaml").write_text("nope: nothing\n", encoding="utf-8")
    rubrics = load_rubrics(tmp_path)
    assert set(rubrics.keys()) == {"claude_md", "agent_prompt"}
    assert isinstance(rubrics["claude_md"], RubricFile)


def test_load_rubrics_missing_dir(tmp_path: Path) -> None:
    assert load_rubrics(tmp_path / "no_such_dir") == {}


def test_rubric_pydantic_strict() -> None:
    r = Rubric(id="x", description="d", severity="P0", action="a")
    assert r.id == "x"
