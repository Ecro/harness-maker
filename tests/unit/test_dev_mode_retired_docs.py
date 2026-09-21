"""AC-008 (SPEC-dev-mode-removal): the removal is announced and the reversal is recorded.

`dev_mode` was a user lock-in ("four crosses all allowed"). Removing it without saying so
would be a decision unlocked by a diff. The announcement form is the existing convention —
a CHANGELOG BREAKING entry, no stub (PLAN-harness-diet ADR-009) — and the reversal lives in a
PLAN ADR.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _changelog_breaking() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    # Announcements remain valid after they move into archived release sections.
    sections = text.split("## [Unreleased]", 1)[1].split("\n## [")
    blocks = []
    for section in sections:
        breaking = section.split("### BREAKING", 1)
        blocks.append(breaking[1].split("\n### ", 1)[0] if len(breaking) == 2 else "")
    return "\n".join(blocks)


def changelog_breaking_entries(term: str) -> int:
    entries = re.split(r"\n(?=- \*\*)", _changelog_breaking())
    return sum(1 for e in entries if term in e)


def plan_adr_mentions(*terms: str) -> bool:
    plan = (ROOT / "work-docs" / "PLAN-dev-mode-removal.md").read_text(encoding="utf-8")
    adrs = re.split(r"\n(?=### ADR-\d+)", plan)
    return any(all(t in adr for t in terms) for adr in adrs if adr.startswith("### ADR-"))


def test_ac_008_removal_is_announced() -> None:
    assert changelog_breaking_entries("dev_mode") >= 1
    assert changelog_breaking_entries("spec.strictness") >= 1
    assert plan_adr_mentions("dev_mode", "revers")
