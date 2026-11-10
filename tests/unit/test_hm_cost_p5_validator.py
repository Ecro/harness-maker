"""SPEC-hm-cost-p5 AC-001, AC-002: the spec check decides whether spec-validator runs by default."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker import spec_machine
from tests.unit import hm_cost_p5_fixture as fx

GOLDEN: dict[str, list[dict[str, Any]]] = json.loads(
    (fx.REPO_ROOT / "specs" / "SPEC-hm-cost-p5.golden.json").read_text(encoding="utf-8")
)
BEFORE: dict[str, dict[str, Any]] = json.loads(fx.BEFORE.read_text(encoding="utf-8"))

#: AC-001's table applied by hand to each fixture's AC count; None = the yaml does not load.
EXPECTED = {"valid_3ac": "skip", "valid_9ac": "run", "failing_gate_9ac": "run", "unloadable": None}


@pytest.mark.parametrize(
    "row", GOLDEN["AC-001"], ids=[f"AC-001-{i}" for i in range(len(GOLDEN["AC-001"]))]
)
def test_validator_verdict(row: dict[str, Any]) -> None:
    assert spec_machine.validator_verdict(fx.model(**row["input"])) == row["expected"]


@pytest.mark.parametrize("name", list(fx.CASES))
def test_ac_002_check_prints_the_verdict(name: str, tmp_path: Path) -> None:
    rc, payload, raw = fx.run_case(tmp_path, name)
    before = BEFORE[name]
    verdict = payload.pop("validator", None)
    assert verdict == EXPECTED[name]
    # everything but the new key is what the unchanged code printed for this fixture
    assert payload == before["payload"]
    assert rc == before["exit"]
    assert raw.count("\n") == before["lines"] == 1
