"""SPEC-hm-cost-p4 AC-009: the first complete tier-1 batch is measured against the 10.0x bar and its
result (met or missed) is recorded in the SPEC; a rerun cannot replace it."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from tests.integration import test_hm_cost_p2_bar as p2

REPO_ROOT = Path(__file__).resolve().parents[2]
# SPEC-hm-cost-p5 moved these rows aside when its own batch became the published one.
RESULTS = REPO_ROOT / "docs" / "evals" / "history" / "hm-cost-p4.jsonl"
BATCHES = REPO_ROOT / "tests" / "fixtures" / "hm_cost_p4" / "batches.json"
SPEC_MD = REPO_ROOT / "specs" / "SPEC-hm-cost-p4.md"
BAR = 10.0
ARMS = ("plain", "hm", "hm-novalidator")


def _counted() -> list[dict[str, Any]]:
    batches = json.loads(BATCHES.read_text(encoding="utf-8"))["batches"]
    first = next(b for b in batches if b["complete"])
    shas = p2.counted_shas(first)
    rows = [json.loads(ln) for ln in RESULTS.read_text(encoding="utf-8").splitlines() if ln]
    return [r for r in rows if any(str(r.get("harness_sha", "")).startswith(s) for s in shas)]


def test_ac_009_tier1_bar_recorded() -> None:
    rows = _counted()
    assert {r["arm"] for r in rows} == set(ARMS)
    nv = [r for r in rows if r["arm"] == "hm-novalidator"]
    assert len(nv) == 15
    per_task = Counter(str(r["task"]) for r in nv)
    assert sorted(per_task.values()) == [3] * 5, per_task
    assert {r["model"] for r in nv} == {p2.MODEL}
    violations = p2.bar_violations([r for r in rows if r["arm"] in ("plain", "hm")], bar=BAR)
    m = re.search(r"\*\*Result \(\d{4}-\d\d-\d\d\): (met|missed)\b", SPEC_MD.read_text("utf-8"))
    assert m is not None, "AC-009's result is not recorded in the SPEC"
    assert m.group(1) == ("missed" if violations else "met"), violations
