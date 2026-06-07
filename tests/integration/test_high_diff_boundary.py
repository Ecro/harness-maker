"""INTEGRATION — LLM boundary accuracy for the high-diff detector (ADR-003, validator W4).

Real LLM call (Claude Code subscription). Gated by INTEGRATION=1 so CI/unit runs skip it.
The deterministic path is covered in tests/unit/test_high_diff.py; this asserts the
LLM adjudicates genuinely-ambiguous boundary diffs above an accuracy floor.
"""

from __future__ import annotations

import os

import pytest

from harness_maker import high_diff

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="set INTEGRATION=1 to run real-LLM boundary accuracy check",
)

# (diff_text, expected_high) — labeled boundary cases that pure numbers can't decide.
_LABELED: list[tuple[str, bool]] = [
    (
        "diff --git a/src/util.py b/src/util.py\n"
        "+def add_public_api_endpoint(request):  # new public entrypoint\n"
        "+    return handle(request)\n",
        True,
    ),
    (
        "diff --git a/src/format.py b/src/format.py\n"
        "+# reflow a long docstring; pure cosmetic, no behavior change\n"
        "+    return value\n",
        False,
    ),
    (
        "diff --git a/src/db.py b/src/db.py\n"
        "+    ALTER TABLE users ADD COLUMN role TEXT  # schema change\n",
        True,
    ),
]

_ACCURACY_FLOOR = 0.66


def test_llm_boundary_accuracy_floor() -> None:
    correct = sum(
        1 for diff, expected in _LABELED if high_diff.judge_boundary_llm(diff) == expected
    )
    accuracy = correct / len(_LABELED)
    assert accuracy >= _ACCURACY_FLOOR, (
        f"boundary accuracy {accuracy:.2f} < floor {_ACCURACY_FLOOR}"
    )
