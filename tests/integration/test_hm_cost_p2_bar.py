"""SPEC-hm-cost-p2 AC-009: the tier-1 re-run on this harness meets the pre-registered 12.5x bar.

The counted rows are pinned by SHA in a committed fixture, matched directly or through a squash
alias checked by tree hash (the `test_overhaul_p1_ship_bar` mechanism), so the bar survives the
wrapup squash and is not met by a later eval's rows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.integration.test_overhaul_p1_ship_bar import _bench, _is_ancestor, _tree

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "docs" / "evals" / "results.jsonl"
PINS = REPO_ROOT / "tests" / "fixtures" / "hm_cost_p2" / "harness_shas.json"
BASELINE_SHA = "473ac3f1"
BAR = 12.5
MODEL = "claude-sonnet-5-5"
RUNS_PER_CELL = 3


def _on_harness(sha: str) -> bool:
    return _is_ancestor(sha, "HEAD") is True and _is_ancestor(sha, BASELINE_SHA) is False


def counted_shas(pins: dict[str, Any]) -> set[str]:
    """Pinned SHAs that stand on this harness, directly or via a tree-checked squash alias."""
    out: set[str] = set()
    for sha in pins["shas"]:
        assert "-dirty-" not in sha, f"pinned sha {sha} is a dirty tree"
        if _on_harness(sha):
            out.add(sha)
            continue
        for alias in pins.get("aliases", []):
            if not alias["source"].startswith(sha):
                continue
            target = alias["target"]
            assert _on_harness(target), f"alias target {target} is not on this harness"
            for part in ("src", "scripts"):
                assert _tree(f"{target}:{part}") == alias[f"{part}_tree"], (target, part)
            out.add(sha)
    return out


def bar_violations(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["no counted eval rows: run the tier-1 bench and pin its harness_sha"]
    bench = _bench()
    out: list[str] = []
    summary = bench.summarize(rows)
    if summary["verdict"] in ("suspect", "no_data"):
        out.append(f"summary verdict is {summary['verdict']}: {summary['why']}")
    hm, plain = summary["arms"]["hm"], summary["arms"]["plain"]
    if not hm["mean_transcript"] or not plain["mean_transcript"]:
        out.append("an arm has no transcript price")
    else:
        ratio = hm["mean_transcript"] / plain["mean_transcript"]
        if round(ratio, 3) > BAR:
            out.append(f"tier-1 transcript ratio {ratio:.3f} > {BAR}")
    tier1 = [r for r in rows if bench.tier_of(r) == 1 and r.get("status") not in bench.UNUSABLE]
    cells: dict[tuple[str, str], int] = {}
    for r in tier1:
        cells[(str(r["task"]), str(r["arm"]))] = cells.get((str(r["task"]), str(r["arm"])), 0) + 1
    expected = {(t.id, a) for t in bench.load_tasks() if t.tier == 1 for a in bench.ARMS}
    for cell in expected:
        cells.setdefault(cell, 0)
    thin = sorted(f"{t}/{a}={n}" for (t, a), n in cells.items() if n != RUNS_PER_CELL)
    if thin:
        out.append(f"cells without {RUNS_PER_CELL} runs: {', '.join(thin)}")
    models = {r.get("model") for r in rows}
    if models != {MODEL}:
        out.append(f"rows are not all {MODEL}: {sorted(map(str, models))}")

    def passed(r: dict[str, Any]) -> bool:
        if r.get("arm") == "hm" and (
            r.get("subtype") == bench.BUDGET_SUBTYPE or r.get("leak_suspect")
        ):
            return False
        return r.get("passed") is True

    rates = {}
    for arm in ("plain", "hm"):
        mine = [r for r in tier1 if r.get("arm") == arm]
        rates[arm] = sum(map(passed, mine)) / len(mine) if mine else 0.0
    if rates["hm"] < rates["plain"]:
        out.append(f"hm pass rate {rates['hm']:.2f} < plain {rates['plain']:.2f}")
    return out


def test_ac_009_tier1_bar() -> None:
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    shas = counted_shas(pins)
    rows = [json.loads(ln) for ln in RESULTS.read_text(encoding="utf-8").splitlines() if ln]
    counted = [r for r in rows if any(str(r.get("harness_sha", "")).startswith(s) for s in shas)]
    assert bar_violations(counted) == []
