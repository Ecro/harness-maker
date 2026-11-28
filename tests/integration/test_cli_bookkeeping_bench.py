"""SPEC-cli-bookkeeping AC-007: the tier-1 bench verdict is computed from the recorded rows.

The rows come from `scripts/bench_light_lane.py run` (tier 1, 3 runs per task, Sonnet 5.5), one
batch for plain + hm on this branch and one for hm on main (124c4c8c) in the same window, reduced
to one line per run by `scripts/bench/cli_bookkeeping_rows.py`. The bar was fixed in the SPEC
before any code; the verdict, met or missed, must be the one the SPEC records.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

REPO = Path(__file__).resolve().parents[2]
ROWS = REPO / "tests" / "fixtures" / "cli_bookkeeping" / "bench_tier1.jsonl"
SPEC = REPO / "specs" / "SPEC-cli-bookkeeping.md"
TASKS = ("t1", "t2", "t3", "t4", "t5")
ARMS = ("plain", "hm-main", "hm-new")


def _rows() -> list[dict[str, Any]]:
    return [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line]


def complete(rows: list[dict[str, Any]]) -> bool:
    usable = [r for r in rows if r["status"] == "ok"]
    return all(
        sum(1 for r in usable if r["arm"] == arm and r["task"] == task) == 3
        for arm in ARMS
        for task in TASKS
    )


def verdict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by = {arm: [r for r in rows if r["arm"] == arm and r["status"] == "ok"] for arm in ARMS}
    cost = {arm: mean(r["cost_usd"] for r in by[arm]) for arm in ARMS}
    wall = {arm: mean(r["wall_s"] for r in by[arm]) for arm in ARMS}
    passes = {arm: sum(1 for r in by[arm] if r["passed"]) for arm in ARMS}
    calls = {arm: mean(r["hm_bash_calls"] for r in by[arm]) for arm in ARMS}
    checks = {
        "cost": cost["hm-new"] <= 0.93 * cost["hm-main"],
        "wall": wall["hm-new"] <= 0.90 * wall["hm-main"],
        "passes": passes["hm-new"] >= passes["plain"],
        "calls": calls["hm-new"] < calls["hm-main"],
    }
    return {
        "verdict": "met" if all(checks.values()) else "missed",
        "checks": checks,
        "cost_ratio_new": round(cost["hm-new"] / cost["plain"], 2),
        "cost_ratio_main": round(cost["hm-main"] / cost["plain"], 2),
    }


def test_ac_007_tier1_bench_verdict_is_recorded() -> None:
    rows = _rows()
    assert complete(rows), "every (task, arm) cell needs 3 usable runs"
    assert all(r["model"] == "claude-sonnet-5-5" for r in rows)
    v = verdict(rows)
    m = re.search(r"^- verdict: (met|missed)$", SPEC.read_text(encoding="utf-8"), re.M)
    assert m, "SPEC has no `- verdict:` line under Measured result"
    assert m.group(1) == v["verdict"], v
