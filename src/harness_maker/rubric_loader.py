"""Load Layer-2 rubric YAML files for LLM-judged content quality.

Rubrics ship under ``templates/rubrics/*.yaml.j2`` and render into the user's
``.claude/rubrics/*.yaml`` so they can be extended per project. Each rubric file
targets one file pattern (CLAUDE.md, agents, skills, workflows) and lists the
content checks the LLM judge should perform.

The on-disk format is multi-doc YAML — doc 1 is the harness provenance
frontmatter, doc 2 is the rubric data. This loader skips the frontmatter doc
and validates the rubric doc against the ``RubricFile`` schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError


class Rubric(BaseModel):
    """One LLM-judged check inside a rubric file."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    description: str
    severity: str  # P0 | P1 | P2
    action: str


class RubricFile(BaseModel):
    """A bundle of rubrics targeting one file pattern."""

    model_config = ConfigDict(strict=True, extra="forbid")

    dimension: str  # readiness dim this augments (e.g., "context_quality")
    target: str  # file pattern (e.g., "CLAUDE.md", ".claude/agents/*.md")
    rubrics: list[Rubric]


def load_rubric_file(path: Path) -> RubricFile | None:
    """Parse a rubric YAML file. Returns None on missing / malformed input."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        docs: list[Any] = list(yaml.safe_load_all(text))
    except yaml.YAMLError:
        return None
    for doc in docs:
        if isinstance(doc, dict) and "rubrics" in doc:
            try:
                return RubricFile.model_validate(doc)
            except ValidationError:
                return None
    return None


def load_rubrics(rubrics_dir: Path) -> dict[str, RubricFile]:
    """Load every ``*.yaml`` rubric file from a directory.

    Returns a mapping of file stem (e.g., ``claude_md``) to ``RubricFile``.
    Files that fail validation are silently skipped — the caller decides whether
    a missing rubric is fatal.
    """
    result: dict[str, RubricFile] = {}
    if not rubrics_dir.is_dir():
        return result
    for f in sorted(rubrics_dir.glob("*.yaml")):
        rf = load_rubric_file(f)
        if rf is not None:
            result[f.stem] = rf
    return result
