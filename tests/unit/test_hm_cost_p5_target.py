"""SPEC-hm-cost-p5 AC-005, AC-007: the cost target is 8 in the bench, intent and objective."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from harness_maker import world
from tests.unit import hm_cost_p5_fixture as fx
from tests.unit import test_bench_light_lane as bench_tests

GOLDEN: dict[str, list[dict[str, Any]]] = json.loads(
    (fx.REPO_ROOT / "specs" / "SPEC-hm-cost-p5.golden.json").read_text(encoding="utf-8")
)
PINNED = ("RESULTS.md", "scorecard.txt", "pre_eval_metric_block.txt")
OBJECTIVE = fx.REPO_ROOT / "intent" / "HM-LIGHT-LANE.md"


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    return bench_tests._load()


@pytest.mark.parametrize(
    "row", GOLDEN["AC-005"], ids=[f"AC-005-{i}" for i in range(len(GOLDEN["AC-005"]))]
)
def test_summarize_judges_against_target_8(bench: ModuleType, row: dict[str, Any]) -> None:
    given, expected = row["input"], row["expected"]
    rows = bench_tests._rows("plain", given["plain"]) + bench_tests._rows(
        "hm", given["hm"], fail=1 if given["hm_pass_below_plain"] else 0
    )
    summary = bench.summarize(rows)
    assert summary["verdict"] == expected["verdict"]
    assert summary["ratio"] == expected["ratio"]
    if not given["hm_pass_below_plain"]:
        assert "target 8" in summary["why"]


def test_ac_005_target_is_8_everywhere_it_is_mirrored(bench: ModuleType) -> None:
    data = yaml.safe_load((fx.REPO_ROOT / ".claude" / "intent.yaml").read_text(encoding="utf-8"))
    metric = next(m for m in data["metrics"] if m["id"] == "hm_cost_ratio_small")
    assert bench.TARGET == 8.0 == metric["target"]
    for name in PINNED:
        rel = f"tests/unit/fixtures/hm_eval/{name}"
        base = subprocess.run(
            ["git", "-C", str(fx.REPO_ROOT), "show", f"{fx.BASE_SHA}:{rel}"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout  # fmt: skip
        assert "target 5" in base, rel
        # one substitution and nothing else: a regenerated fixture cannot agree with itself
        assert (fx.REPO_ROOT / rel).read_text(encoding="utf-8") == base.replace(
            "target 5", "target 8"
        ), rel


def test_ac_005_report_pin_moved_by_the_substitution_only(
    bench: ModuleType, tmp_path: Path
) -> None:
    """The eval-3 report, with the target put back, hashes to the pin recorded before this SPEC."""
    eval3 = subprocess.run(
        ["git", "-C", str(fx.REPO_ROOT), "show", "db19f023:docs/evals/results.jsonl"],
        capture_output=True, text=True, timeout=60, check=True,
    ).stdout  # fmt: skip
    (tmp_path / "results.jsonl").write_text(eval3, encoding="utf-8")
    report = bench.report_text(bench.read_rows(tmp_path))
    assert report.count("target 8") == 1
    restored = report.replace("target 8", "target 5")
    assert hashlib.sha256(restored.encode()).hexdigest()[:16] == "a082ce5d4abd734b"


def test_ac_007_objective_states_target_8_and_is_approved() -> None:
    doc = OBJECTIVE.read_text(encoding="utf-8")
    for token in ("22 → 8 이하", "8배 이하", "배수 ≤ 8", "배수 > 8"):
        assert token in doc, token
    for token in ("5 이하", "5배", "≤ 5", "> 5", "light 에서도 돈다"):
        assert token not in doc, token
    assert "AC 8개 이하 SPEC 은 기본 생략, 승인 때 DRI 가 고르면 실행" in doc
    front = yaml.safe_load(doc.split("---", 2)[1])
    assert front["approval"]["approved_target"] == 8
    loaded = world.load_world(fx.REPO_ROOT)
    assert world.derive(loaded, "HM-LIGHT-LANE").approval_valid is True
