"""Phase C1 structural gate: reviewer prompts carry the locked agentic-depth substrings.

PLAN-llm-code-review-2026 ADR-009 Decision #1 locks an exact substring contract
for the 5 reviewer prompt bodies. The 3 common substrings instruct full-context
Read, Grep-to-confirm, and git-log-for-intent. The 4th per-reviewer substring
verifies the agentic depth is meaningfully customised for each domain
(not the same generic instruction pasted into 5 files).

Source-of-truth contract: ADR-009 Decision #1 substring contract table in
work-docs/PLAN-llm-code-review-2026.md. Re-introducing or removing a
substring requires a new ADR superseding ADR-009.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = REPO_ROOT / "src/harness_maker/templates/agents"

COMMON_SUBSTRINGS: tuple[str, ...] = (
    "Read changed files end-to-end",
    "Grep to confirm before flagging",
    "git log for prior intent",
)

REVIEWER_SPECIFIC: dict[str, str] = {
    "code-reviewer": "trace runtime path",
    "security-reviewer": "Grep for related sinks",
    "performance-reviewer": "Grep for hot-path callers",
    "concurrency-reviewer": "Grep for lock acquisitions",
    "ux-reviewer": "Grep for related accessibility patterns",
}


@pytest.mark.parametrize(
    ("reviewer", "specific_phrase"),
    [
        ("code-reviewer", "trace runtime path"),
        ("concurrency-reviewer", "Grep for lock acquisitions"),
        ("performance-reviewer", "Grep for hot-path callers"),
        ("security-reviewer", "Grep for related sinks"),
        ("ux-reviewer", "Grep for related accessibility patterns"),
    ],
)
def test_reviewer_prompt_contains_agentic_depth_clauses(
    reviewer: str, specific_phrase: str
) -> None:
    body_path = AGENTS_ROOT / f"{reviewer}_body.md.j2"
    assert body_path.is_file(), f"missing reviewer body template: {body_path}"
    body = body_path.read_text(encoding="utf-8")

    for substring in COMMON_SUBSTRINGS:
        assert substring in body, (
            f"{reviewer}_body.md.j2 missing common agentic-depth substring "
            f"{substring!r} (ADR-009 Decision #1 substring contract)"
        )

    assert specific_phrase in body, (
        f"{reviewer}_body.md.j2 missing reviewer-specific substring "
        f"{specific_phrase!r} (ADR-009 Decision #1 substring contract)"
    )
