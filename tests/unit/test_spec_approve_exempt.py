"""SPEC-hm-light-lane-s3a AC-014 (CLI half) — an exempt stamp never covers an irreversible decision.

`approval_state_of` already reads an exempt stamp with irreversible ids as `invalid` (e7dd6648);
refusing at write time keeps `/hm:spec`'s light-lane stamp from producing that state at all.
"""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import pytest
import yaml

from harness_maker import spec_machine
from harness_maker.spec_machine import load
from tests.unit.light_lane_s3a_fixture import MACHINE_DOC

IRR = [{"id": "IRR-001", "decision": "d", "category": "c", "rationale": "r", "source": "spec"}]


@pytest.fixture
def spec_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repo"
    (root / "specs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    return root / "specs" / "SPEC-demo.machine.yaml"


def _write(path: Path, irreversible: list[dict[str, str]]) -> None:
    doc = copy.deepcopy(MACHINE_DOC)
    doc["irreversible_decisions"] = irreversible
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def test_exempt_refuses_irreversible_decisions(
    spec_yaml: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(spec_yaml, IRR)
    rc = spec_machine.main(["approve", "--yaml", str(spec_yaml), "--exempt"])
    assert rc != 0
    assert load(spec_yaml).approval is None
    assert "IRR-001" in capsys.readouterr().err


def test_exempt_still_stamps_an_empty_list(spec_yaml: Path) -> None:
    _write(spec_yaml, [])
    assert spec_machine.main(["approve", "--yaml", str(spec_yaml), "--exempt"]) == 0
    stamp = load(spec_yaml).approval
    assert stamp is not None
    assert stamp.kind == "exempt"
