"""SPEC-hm-overhaul-p1 AC-010: the published eval re-run meets the DRI's ship bar.

Reads the committed `docs/evals/results.jsonl` and keeps the rows whose `harness_sha` is
reachable from HEAD but not from db19f023, i.e. rows measured on this overhaul's harness. With no
such rows the test fails and never skips: the committed scorecard is PR-S's ship gate.
Predicate (the DRI's 2026-10-15 bar): tier-1 cost ratio <= 8, and on tiers 1-2 hm's hidden-test
pass rate >= plain's. The ratio is `bench_light_lane.summarize`'s judged ratio (the larger of the
CLI and transcript ratios), so the gate and the published number are one computation.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from functools import cache
from types import ModuleType
from typing import Any

from tests._overhaul_p1_ref import REF_SHA, REPO_ROOT

RESULTS = REPO_ROOT / "docs" / "evals" / "results.jsonl"
_SCRIPT = REPO_ROOT / "scripts" / "bench_light_lane.py"
MAX_T1_RATIO = 8.0


@cache
def _bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_light_lane", _SCRIPT)
    assert spec is not None, f"missing {_SCRIPT}"
    assert spec.loader is not None, f"missing {_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_light_lane"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


def _is_ancestor(sha: str, of: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", sha, of],
        capture_output=True,
        timeout=60,
        check=False,
    )
    return proc.returncode == 0  # 1 = not an ancestor, 128 = unknown sha: neither counts


@cache
def _on_this_harness(sha: str) -> bool:
    return _is_ancestor(sha, "HEAD") and not _is_ancestor(sha, REF_SHA)


def _rows() -> list[dict[str, Any]]:
    lines = RESULTS.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    return [
        r
        for r in rows
        if isinstance(r.get("harness_sha"), str) and _on_this_harness(r["harness_sha"])
    ]


def ship_bar_violations(rows: list[dict[str, Any]]) -> list[str]:
    """Why `rows` miss the bar; empty when they meet it."""
    if not rows:
        return ["no eval rows on a harness SHA reachable from HEAD and not from db19f023"]
    bench = _bench()
    out: list[str] = []
    ratio = bench.summarize(rows).get("judged_ratio")
    if ratio is None:
        out.append("tier 1 has no priced plain/hm pair, so the cost ratio is undefined")
    elif ratio > MAX_T1_RATIO:
        out.append(f"tier-1 cost ratio {ratio:.3f} > {MAX_T1_RATIO:g}")
    usable = [
        r for r in rows if r.get("status") not in bench.UNUSABLE and bench.tier_of(r) in (1, 2)
    ]
    rates: dict[str, float] = {}
    for arm in ("plain", "hm"):
        mine = [r for r in usable if r.get("arm") == arm]
        if not mine:
            out.append(f"tiers 1-2 have no usable {arm} runs")
            continue
        rates[arm] = sum(1 for r in mine if r.get("passed") is True) / len(mine)
    if len(rates) == 2 and rates["hm"] < rates["plain"]:
        out.append(f"hm hidden pass rate {rates['hm']:.3f} < plain {rates['plain']:.3f}")
    return out


def test_ac010_scorecard_meets_bar() -> None:
    violations = ship_bar_violations(_rows())
    assert not violations, "\n".join(violations)


def _row(arm: str, task: str, cost: float, passed: bool, rep: int) -> dict[str, Any]:
    return {
        "bench": "hm-light-lane",
        "bench_hash": "b",
        "harness_sha": "h",
        "runner_hash": "r",
        "model": "m",
        "tier": 1,
        "task": task,
        "arm": arm,
        "rep": rep,
        "status": "ok",
        "cost_usd": cost,
        "transcript_cost_usd": cost,
        "transcript_turns": 3,
        "passed": passed,
    }


def test_ac010_predicate_controls() -> None:
    """The bar is two-sided: a cheap-enough hm arm passes, a 9x or a lower pass rate does not."""

    def rows(hm_cost: float, hm_passed: bool) -> list[dict[str, Any]]:
        return [_row("plain", "t1", 1.0, True, i) for i in range(3)] + [
            _row("hm", "t1", hm_cost, hm_passed, i) for i in range(3)
        ]

    assert ship_bar_violations(rows(5.0, True)) == []
    assert any("cost ratio" in v for v in ship_bar_violations(rows(9.0, True)))
    assert any("pass rate" in v for v in ship_bar_violations(rows(2.0, False)))
    assert ship_bar_violations([])
