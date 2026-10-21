"""SPEC-hm-cost-p2 AC-001 (export-golden) and AC-005 (approval in `spec_machine check`)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from harness_maker import spec_machine
from tests.hm_cost_p2_fixture import REPO_ROOT, init_project, mech_ac, param_ac, write_spec

# Hand-written: AC-002 is superseded and AC-003 is mechanical, so only AC-001 is exported, and
# its rows lose `edge`/`note` and any extra key.
EXPECTED_LITERAL = {
    "AC-001": [
        {"input": {"s": "1h"}, "expected": 3600},
        {"input": {"s": "2m"}, "expected": 120},
    ]
}


# The same rows as bytes: keys sorted at every level ("expected" before "input").
EXPECTED_TEXT = """{
  "AC-001": [
    {
      "expected": 3600,
      "input": {
        "s": "1h"
      }
    },
    {
      "expected": 120,
      "input": {
        "s": "2m"
      }
    }
  ]
}
"""


def _export(yaml_path: Path) -> int:
    return spec_machine.main(["export-golden", "--yaml", str(yaml_path)])


def test_ac_001_export_golden(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = init_project(tmp_path / "p")
    rows = [
        {"input": {"s": "1h"}, "expected": 3600, "edge": True, "note": "hour", "why": "x"},
        {"input": {"s": "2m"}, "expected": 120},
    ]
    yaml_path = write_spec(
        root,
        [
            param_ac("AC-001", rows),
            param_ac("AC-002", [{"input": {"s": "9s"}, "expected": 9}], superseded_by="other"),
            mech_ac("AC-003"),
        ],
    )
    out = root / "specs" / "SPEC-demo.golden.json"

    assert _export(yaml_path) == 0
    first = out.read_bytes()
    assert json.loads(first) == EXPECTED_LITERAL
    assert first.decode() == EXPECTED_TEXT
    assert _export(yaml_path) == 0
    assert out.read_bytes() == first

    bare = init_project(tmp_path / "bare")
    bare_yaml = write_spec(bare, [mech_ac("AC-001")])
    assert _export(bare_yaml) == 0
    assert not (bare / "specs" / "SPEC-demo.golden.json").exists()

    dated = init_project(tmp_path / "dated")
    dated_yaml = write_spec(dated, [param_ac("AC-001", [{"input": {"s": "x"}, "expected": 1}])])
    text = dated_yaml.read_text(encoding="utf-8").replace("expected: 1", "expected: 2026-10-21")
    dated_yaml.write_text(text, encoding="utf-8")
    capsys.readouterr()
    assert _export(dated_yaml) != 0
    err = capsys.readouterr().err
    assert "AC-001" in err, err
    assert "row 0" in err, err
    assert not (dated / "specs" / "SPEC-demo.golden.json").exists()


def test_export_golden_refuses_a_key_json_would_rewrite(tmp_path: Path) -> None:
    """An int mapping key becomes a string in JSON, so the exported oracle would differ."""
    root = init_project(tmp_path / "p")
    yaml_path = write_spec(
        root, [param_ac("AC-001", [{"input": {"s": "x"}, "expected": {1: "one"}}])]
    )
    assert _export(yaml_path) != 0
    assert not (root / "specs" / "SPEC-demo.golden.json").exists()

    mixed = init_project(tmp_path / "mixed")
    mixed_yaml = write_spec(
        mixed, [param_ac("AC-001", [{"input": {"s": "x"}, "expected": {1: "a", "b": 2}}])]
    )
    assert _export(mixed_yaml) != 0


@pytest.fixture
def approved_root(tmp_path: Path) -> Path:
    """A copy of this task's own approved SPEC: a real stamp over real content."""
    root = init_project(tmp_path / "p")
    (root / "specs").mkdir()
    for name in ("SPEC-hm-cost-p2.md", "SPEC-hm-cost-p2.machine.yaml"):
        shutil.copy(REPO_ROOT / "specs" / name, root / "specs" / name)
    return root


def _last_json(text: str) -> dict[str, object]:
    line = [ln for ln in text.splitlines() if ln.strip()][-1]
    parsed: dict[str, object] = json.loads(line)
    return parsed


def test_ac_005_check_carries_approval(
    approved_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = approved_root / "specs"
    spec_machine.main(
        [
            "check", "--all",
            "--yaml", str(specs / "SPEC-hm-cost-p2.machine.yaml"),
            "--md", str(specs / "SPEC-hm-cost-p2.md"),
        ]
    )  # fmt: skip
    check_out = _last_json(capsys.readouterr().out)
    spec_machine.main(["approval-status", "--root", str(approved_root), "--slug", "hm-cost-p2"])
    status_out = _last_json(capsys.readouterr().out)
    approval = check_out["approval"]
    assert isinstance(approval, dict)
    keys = ("state", "land", "gate")
    assert {k: approval[k] for k in keys} == {k: status_out[k] for k in keys}
    assert approval["state"] == "approved"
