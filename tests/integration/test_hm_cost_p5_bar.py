"""SPEC-hm-cost-p5 AC-006: the first mechanically complete tier-1 batch is judged by the metric's
own rule at target 8, and whatever it returns is the result recorded in the SPEC."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from tests.integration import test_hm_cost_p4_bar as p4
from tests.unit import test_bench_light_lane as bench_tests

REPO_ROOT = Path(__file__).resolve().parents[2]
BATCHES = REPO_ROOT / "tests" / "fixtures" / "hm_cost_p5" / "batches.json"
SPEC_MD = REPO_ROOT / "specs" / "SPEC-hm-cost-p5.md"
ARMS = ("plain", "hm")
MODEL = "claude-sonnet-5-5"
RUNS = 3
TIER1_TASKS = 5
UNUSABLE = ("setup_error", "runner_error")


def _rows(rel: str) -> list[dict[str, Any]]:
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def _complete(rows: list[dict[str, Any]]) -> bool:
    """Recomputed from the rows, so the fixture's own flag cannot set a batch aside."""
    cells = Counter((str(r["task"]), str(r["arm"])) for r in rows)
    return (
        {arm for _, arm in cells} == set(ARMS)
        and len({task for task, _ in cells}) == TIER1_TASKS
        and len(cells) == TIER1_TASKS * len(ARMS)
        and set(cells.values()) == {RUNS}
        and not any(r.get("status") in UNUSABLE for r in rows)
        and {r.get("model") for r in rows} == {MODEL}
    )


def test_ac_006_tier1_result_recorded() -> None:
    batches = json.loads(BATCHES.read_text(encoding="utf-8"))["batches"]
    loaded = [(b, _rows(b["rows"])) for b in batches]
    for batch, rows in loaded:
        assert batch["complete"] == _complete(rows), batch["run"]
    counted_batch, counted = next((b, rows) for b, rows in loaded if _complete(rows))
    # the counted batch is the one the published RESULTS.md is rendered from
    assert counted_batch["rows"] == "docs/evals/results.jsonl"
    summary = bench_tests._load().summarize(counted)
    text = SPEC_MD.read_text(encoding="utf-8")
    m = re.search(
        r"\*\*Result \(\d{4}-\d\d-\d\d\): (met|missed|suspect|no_data)\.\*\*"
        r"(?: Judged ratio (\d+\.\d{3})\b)?",
        text,
    )
    assert m is not None, "AC-006's result is not recorded in the SPEC"
    assert m.group(1) == summary["verdict"]
    ratio = summary.get("ratio")
    assert m.group(2) == (None if ratio is None else f"{ratio:.3f}")
    # p4's rows moved to history and its own bar test still reads them
    assert p4.RESULTS == REPO_ROOT / "docs" / "evals" / "history" / "hm-cost-p4.jsonl"
    assert p4.RESULTS.is_file()
