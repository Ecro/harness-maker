"""Phase B5 — the net-surface assertion for PLAN-workflow-time-token-savings.

ADR-008.4. Stage 1 of this line of work (PLAN-workflow-loop-efficiency) grew the shipped
surface by +7,113 chars on an explicit condition: *"only pays for itself if stage 2 actually
reads those ledgers and deletes something."* This PLAN is stage 2, and this is the only
artifact that can report the answer as a pass or a fail rather than as prose.

**It must be able to fail.** The earlier draft of this criterion said "assert it, or record it
red", and a disjunction whose second branch is "write it down" is not an assertion. If the PLAN
ends net-positive the permitted escape is an explicit `xfail` carrying a waiver that references
the closing BASELINE-DELTA row — visible in every CI run — never a re-freeze of the baseline it
is measuring (`[fail:test] ratchet-rebaselined-by-its-own-subject`, count:2).

The literal below is read from the BASELINE-DELTA document rather than hard-coded here, so the
number this asserts against and the number the PLAN records cannot drift apart.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BASELINE = REPO_ROOT / "tests" / "structural" / "surface_baseline.json"
_DELTA = REPO_ROOT / "work-docs" / "BASELINE-DELTA-workflow-time-token-savings.md"


def _pre_plan_literal(key: str) -> int:
    """The pre-PLAN value from §0 of the BASELINE-DELTA table."""
    row = re.search(
        rf"^\|\s*`aggregate_chars\.{key}`\s*\|\s*\*\*(\d+)\*\*\s*\|",
        _DELTA.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert row is not None, f"§0 of {_DELTA.name} no longer records a literal for {key}"
    return int(row.group(1))


def _frozen(key: str) -> int:
    value = json.loads(_BASELINE.read_text(encoding="utf-8"))["aggregate_chars"][key]
    assert isinstance(value, int)
    return value


def test_the_delta_document_still_carries_its_anchor() -> None:
    """Guards the guard: a reformatted table would make the regex return nothing, and an
    assertion that cannot find its own baseline passes for the wrong reason."""
    assert _pre_plan_literal("claude") == 366439
    assert _pre_plan_literal("codex") == 299602


# The waiver xfail that stood here (PLAN-workflow-time-token-savings ADR-008.4: claude ended
# 366439 → 371066, +4627) is removed, not re-frozen: SPEC-hm-overhaul-p1 PR-S collapsed the
# stages and re-froze the baseline at claude 45487 / codex 27381 (BASELINE-DELTA-hm-overhaul-p1-s),
# so both variants now hold the assertion by a wide margin and the strict=False marker was
# reporting XPASS. Kept as an xfail it would also hide a real regression past the anchor.
@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_the_plan_did_not_grow_the_shipped_surface(variant: str) -> None:
    before = _pre_plan_literal(variant)
    now = _frozen(variant)
    assert now <= before, (
        f"{variant}: PLAN-workflow-time-token-savings ended net-positive "
        f"({before} → {now}, +{now - before}). Either the growth is unintended — B3 and B4 add "
        "surface and A3/A5 are the only reductions — or it is accepted, in which case mark "
        "THIS test xfail with a waiver referencing the closing row in "
        "BASELINE-DELTA-workflow-time-token-savings.md §3. Do NOT re-freeze "
        "surface_baseline.json to make it pass: the ratchet cannot be rebaselined by the "
        "change it exists to measure."
    )
