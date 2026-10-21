"""SPEC-hm-cost-p3 AC-005: the tier-1 re-run was measured against the pre-registered 10.0x bar and
its miss is recorded; AC-006: the hm-cost-p2 rows survive the replacement in docs/evals/history and
keep p2's bar green."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.integration import test_hm_cost_p2_bar as p2

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "docs" / "evals" / "results.jsonl"
PINS = REPO_ROOT / "tests" / "fixtures" / "hm_cost_p3" / "harness_shas.json"
P2_HISTORY = REPO_ROOT / "docs" / "evals" / "history" / "hm-cost-p2.jsonl"
P2_LANDED = "022d6f2a"
BAR = 10.0
# The DRI landed the task with the miss recorded (2026-10-22); the bar itself was not moved.
RECORDED_MISS = ["tier-1 transcript ratio 11.359 > 10.0"]


def _counted() -> list[dict[str, object]]:
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    shas = p2.counted_shas(pins)
    rows = [json.loads(ln) for ln in RESULTS.read_text(encoding="utf-8").splitlines() if ln]
    return [r for r in rows if any(str(r.get("harness_sha", "")).startswith(s) for s in shas)]


def test_ac_005_tier1_bar_miss_recorded() -> None:
    # The ratio is the only violation: every guard holds, and a later run that meets the bar
    # (or misses it by another amount) fails here until this record is updated.
    assert p2.bar_violations(_counted(), bar=BAR) == RECORDED_MISS


def test_ac_006_p2_history() -> None:
    landed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{P2_LANDED}:docs/evals/results.jsonl"],
        capture_output=True, timeout=60, check=True,
    ).stdout  # fmt: skip
    assert P2_HISTORY.read_bytes() == landed
    assert p2.RESULTS == P2_HISTORY
    p2.test_ac_009_tier1_bar()
