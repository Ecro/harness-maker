"""SPEC-docs-rewrite: living docs describe the four live stages and no deleted module."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_HOW = ("docs/HOW-IT-WORKS.md", "docs/HOW-IT-WORKS.ko.md")
_STAGES = ("/hm:research", "/hm:spec", "/hm:execute", "/hm:wrapup")
#: Headings the 0.64.0 guide still gave whole sections to, as if live.
_RETIRED_HEADINGS = re.compile(
    r"^#{2,4} (?!.*retired|.*은퇴).*\b(hm:loop|hm:review|hm:verify|hm:configure|6 atomic|autopilot"
    r"|stuck|executor|security-auditor|autoloop-coder|conditional router|plan-validator)\b",
    re.M | re.I,
)
#: Modules deleted by SPEC-dead-modules; a living doc must not list them as present.
_DELETED = re.compile(
    r"(?<![\w/])(foreign_config|provenance|relevance)\.py\b|templates/foreign-configs"
)
#: Docs that may name a deleted module only in a sentence that says it was deleted.
_LIVING = (
    "README.md",
    "README.ko.md",
    "docs/ARCHITECTURE.md",
    "docs/CONTRIBUTING.md",
    "docs/reference/autoloop-pattern.md",
    "docs/reference/block-merge-spec.md",
    *_HOW,
)


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_ac_001_how_it_works_has_a_section_per_live_stage() -> None:
    per_locale = []
    for rel in _HOW:
        headings = re.findall(r"^#{2,4} .*$", _read(rel), re.M)
        for stage in _STAGES:
            assert sum(f"`{stage}`" in h for h in headings) == 1, (rel, stage)
        per_locale.append(len(re.findall(r"^## ", _read(rel), re.M)))
    assert per_locale[0] == per_locale[1], per_locale  # the locales keep the same sections


def test_ac_001_how_it_works_gives_no_retired_piece_a_live_section() -> None:
    for rel in _HOW:
        found = _RETIRED_HEADINGS.findall(_read(rel))
        assert found == [], (rel, found)


def test_ac_001_living_docs_list_no_deleted_module() -> None:
    for rel in _LIVING:
        for line in _read(rel).splitlines():
            if _DELETED.search(line):
                assert re.search(r"deleted|retired|삭제|은퇴", line, re.I), (rel, line)
