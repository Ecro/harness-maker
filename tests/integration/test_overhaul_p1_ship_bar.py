"""SPEC-hm-overhaul-p1 AC-010: the published eval re-run meets the DRI's ship bar.

Reads the committed `docs/evals/results.jsonl` and keeps the rows whose `harness_sha` is
reachable from HEAD but not from db19f023, i.e. rows measured on this overhaul's harness. With no
such rows the test fails and never skips: the committed scorecard is PR-S's ship gate.
Predicate (amended by the DRI's card of 2026-10-16, after the re-run missed the 2026-10-15 bar of
<= 8): tier-1 cost ratio below the eval-3 baseline of 26.418, and on tiers 1-2 hm's hidden-test
pass rate >= plain's. 8x is the phase-2 target. The ratio is `bench_light_lane.summarize`'s
judged ratio (the larger of the CLI and transcript ratios), so the gate and the published number
are one computation.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from functools import cache
from types import ModuleType
from typing import Any

import pytest

from tests._overhaul_p1_ref import REF_SHA, REPO_ROOT

RESULTS = REPO_ROOT / "docs" / "evals" / "results.jsonl"
_SCRIPT = REPO_ROOT / "scripts" / "bench_light_lane.py"
#: The eval-3 tier-1 judged ratio, the last one published before this phase: `summarize` over
#: docs/evals/results.jsonl as committed in db19f023 (harness 6b7c30d9e175) gives 26.4177,
#: published as 26.418 in that commit's RESULTS.md.
EVAL3_T1_RATIO = 26.418


@cache
def _bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_light_lane", _SCRIPT)
    assert spec is not None, f"missing {_SCRIPT}"
    assert spec.loader is not None, f"missing {_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_light_lane"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


class UnknownCommitError(AssertionError):
    """A SHA git does not know: never read as "not an ancestor"."""


class BadAliasError(AssertionError):
    """A squash alias whose target is off this harness or whose trees differ."""


def _is_ancestor(sha: str, of: str) -> bool | None:
    """True/False from `merge-base --is-ancestor`; None when git exits otherwise (128: unknown)."""
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", sha, of],
        capture_output=True,
        timeout=60,
        check=False,
    )
    return {0: True, 1: False}.get(proc.returncode)


ALIASES = REPO_ROOT / "tests" / "fixtures" / "overhaul_p1" / "harness_sha_aliases.json"


def load_aliases() -> list[dict[str, str]]:
    data: list[dict[str, str]] = json.loads(ALIASES.read_text(encoding="utf-8"))
    return data


def _tree(rev: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", "--quiet", rev],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def _reachable(sha: str, ref: str) -> bool:
    if _is_ancestor(ref, "HEAD") is None:
        raise UnknownCommitError(
            f"reference commit {ref} is unknown to this clone (fetch-depth: 0?)"
        )
    return _is_ancestor(sha, "HEAD") is True and _is_ancestor(sha, ref) is False


def alias_problem(entry: dict[str, str], ref: str = REF_SHA) -> str | None:
    """Why a squash alias cannot stand in for its source, or None. Checked by tree hash, so it
    holds in a clone that no longer has the squashed source commit."""
    target = entry["target"]
    if not _reachable(target, ref):
        return f"alias target {target} is not on this harness"
    for rev in (target, entry["source"]):
        if rev == entry["source"] and _tree(f"{rev}^{{commit}}") is None:
            continue  # the squashed source is gone from this clone; the target carries the proof
        for part in ("src", "scripts"):
            if _tree(f"{rev}:{part}") != entry[f"{part}_tree"]:
                return f"{rev}:{part} is not the recorded tree {entry[f'{part}_tree']}"
    return None


@cache
def on_this_harness(sha: str, ref: str = REF_SHA) -> bool:
    """Reachable from HEAD and not from the reference, directly or through a squash alias. An
    unknown reference fails the gate: read as "not an ancestor", it would count every
    HEAD-reachable row. An unknown row SHA (a commit not in this clone, with no alias) is simply
    not this harness; a broken alias fails the gate."""
    if _reachable(sha, ref):
        return True
    for entry in load_aliases():
        # Rows record an abbreviated SHA (`harness_sha` is 12 hex digits).
        if len(sha) >= 7 and entry["source"].startswith(sha):
            problem = alias_problem(entry, ref)
            if problem is not None:
                raise BadAliasError(problem)
            return True
    return False


def _rows() -> list[dict[str, Any]]:
    lines = RESULTS.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    return [
        r
        for r in rows
        if isinstance(r.get("harness_sha"), str) and on_this_harness(r["harness_sha"])
    ]


#: SPEC S7: the re-run is 3 runs per (task, arm) cell.
MIN_RUNS_PER_CELL = 3


def ship_bar_violations(rows: list[dict[str, Any]]) -> list[str]:
    """Why `rows` miss the bar; empty when they meet it."""
    if not rows:
        return ["no eval rows on a harness SHA reachable from HEAD and not from db19f023"]
    bench = _bench()
    out: list[str] = []
    summary = bench.summarize(rows)
    if summary.get("verdict") in ("suspect", "no_data"):
        out.append(f"the tier-1 summary is {summary['verdict']}: {summary.get('why')}")
    ratio = summary.get("judged_ratio")
    if ratio is None:
        out.append("tier 1 has no priced plain/hm pair, so the cost ratio is undefined")
    elif round(ratio, 3) >= EVAL3_T1_RATIO:
        # Compared at the published precision: eval 3's own unrounded 26.4177 must not pass.
        out.append(f"tier-1 cost ratio {ratio:.3f} is not below the eval-3 {EVAL3_T1_RATIO:g}")
    usable = [
        r for r in rows if r.get("status") not in bench.UNUSABLE and bench.tier_of(r) in (1, 2)
    ]
    cells: dict[tuple[str, str], int] = {}
    for r in usable:
        key = (str(r.get("task")), str(r.get("arm")))
        cells[key] = cells.get(key, 0) + 1
    thin = sorted(f"{t}/{a}={n}" for (t, a), n in cells.items() if n < MIN_RUNS_PER_CELL)
    if thin:
        out.append(f"fewer than {MIN_RUNS_PER_CELL} runs per cell: {', '.join(thin)}")

    def passed(r: dict[str, Any]) -> bool:
        # A capped or leak-suspect hm run biases the pass rate in hm's favour: never a pass.
        if r.get("arm") == "hm" and (
            r.get("subtype") == bench.BUDGET_SUBTYPE or r.get("leak_suspect")
        ):
            return False
        return r.get("passed") is True

    rates: dict[str, float] = {}
    for arm in ("plain", "hm"):
        mine = [r for r in usable if r.get("arm") == arm]
        if not mine:
            out.append(f"tiers 1-2 have no usable {arm} runs")
            continue
        rates[arm] = sum(1 for r in mine if passed(r)) / len(mine)
    if len(rates) == 2 and rates["hm"] < rates["plain"]:
        out.append(f"hm hidden pass rate {rates['hm']:.3f} < plain {rates['plain']:.3f}")
    return out


def test_ac010_scorecard_meets_bar() -> None:
    violations = ship_bar_violations(_rows())
    assert not violations, "\n".join(violations)


def _row(arm: str, task: str, cost: float, passed: bool, rep: int, **extra: Any) -> dict[str, Any]:
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
        **extra,
    }


def test_ac010_predicate_controls() -> None:
    """The bar is two-sided: a ratio below the eval-3 baseline passes, a ratio at or above it, or
    a lower pass rate, does not. 12.97 is the measured PR-S ratio, which the 8x bar rejected."""

    def rows(hm_cost: float, hm_passed: bool) -> list[dict[str, Any]]:
        return [_row("plain", "t1", 1.0, True, i) for i in range(3)] + [
            _row("hm", "t1", hm_cost, hm_passed, i) for i in range(3)
        ]

    assert ship_bar_violations(rows(5.0, True)) == []
    assert ship_bar_violations(rows(12.97, True)) == []
    assert any("cost ratio" in v for v in ship_bar_violations(rows(EVAL3_T1_RATIO, True)))
    assert any("cost ratio" in v for v in ship_bar_violations(rows(27.0, True)))
    assert any("pass rate" in v for v in ship_bar_violations(rows(2.0, False)))
    assert ship_bar_violations([])


def test_ac010_the_eval3_scorecard_itself_does_not_pass() -> None:
    """The baseline's own rows sit at the baseline, so they miss a bar that asks for less."""
    text = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{REF_SHA}:docs/evals/results.jsonl"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    assert any("cost ratio" in v for v in ship_bar_violations(rows))


def test_ac010_untrusted_scorecards_do_not_pass() -> None:
    """A `suspect` or `no_data` summary, a capped or leak-suspect hm pass, or fewer than 3 runs
    per cell never meets the bar, however good the numbers look (SPEC S7: 3 runs per cell)."""
    plain = [_row("plain", "t1", 1.0, True, i) for i in range(3)]

    leak = plain + [_row("hm", "t1", 2.0, True, i, leak_suspect=i == 0) for i in range(3)]
    assert any("suspect" in v for v in ship_bar_violations(leak))

    capped = plain + [
        _row("hm", "t1", 2.0, True, i, subtype="error_max_budget_usd" if i == 0 else "success")
        for i in range(3)
    ]
    found = ship_bar_violations(capped)
    assert any("suspect" in v for v in found), found
    assert any("pass rate" in v for v in found), "a capped hm run is not a pass"

    thin = [_row(a, "t1", c, True, i) for a, c in (("plain", 1.0), ("hm", 2.0)) for i in range(2)]
    assert any("runs per cell" in v for v in ship_bar_violations(thin))

    tier2_thin = [*plain, *(_row("hm", "t1", 2.0, True, i) for i in range(3))] + [
        {**_row(a, "t7", 1.0, True, 0), "tier": 2} for a in ("plain", "hm")
    ]
    assert any("runs per cell" in v for v in ship_bar_violations(tier2_thin))

    unbalanced = plain + [_row("hm", "t1", 2.0, True, i) for i in range(4)]
    assert any("no_data" in v for v in ship_bar_violations(unbalanced))


def test_ac010_an_unknown_reference_commit_fails() -> None:
    """`merge-base --is-ancestor` exits 128 for an unknown SHA; read as "not an ancestor", every
    HEAD-reachable row would count as measured on this harness."""
    head = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout.strip()
    with pytest.raises(UnknownCommitError):
        on_this_harness(head, ref="0" * 40)
    assert on_this_harness(head, ref=REF_SHA) is True


#: SPEC-retired-text AC-005: the eval-4 harness commit PR #36's squash left off main.
SQUASHED_PR_S_HARNESS = "a2fe560a401846f8ab161662382d7f994ec5f91c"


def test_ac_005_alias_counts_only_with_matching_trees() -> None:
    aliases = load_aliases()
    assert [a["source"] for a in aliases] == [SQUASHED_PR_S_HARNESS]
    good = aliases[0]
    assert alias_problem(good) is None
    assert on_this_harness(SQUASHED_PR_S_HARNESS) is True
    assert on_this_harness(SQUASHED_PR_S_HARNESS[:12]) is True
    assert on_this_harness("0" * 40) is False
    # A target on the reference harness (db19f023 itself) is not this harness.
    ref_full = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", REF_SHA],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout.strip()
    assert alias_problem({**good, "target": ref_full}) is not None
    assert alias_problem({**good, "src_tree": "0" * 40}) is not None
    assert alias_problem({**good, "scripts_tree": "0" * 40}) is not None
    # A source this clone no longer has is skipped; the target's trees carry the proof.
    assert alias_problem({**good, "source": "0" * 40}) is None
    # A source git knows must carry the recorded trees too.
    assert alias_problem({**good, "source": ref_full}) is not None
