"""SPEC-ai-native-sdlc-vs-intent-world AC-003 — the spec boundary follows the SPEC, not the caller.

Golden rows come from the machine SPEC (the gate column of the SPEC's state table plus the
Round 1 / Revision 1 decisions), loaded at collection time. The one property a caller must not
be able to buy is a `clear` for a SPEC nobody accepted.
"""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import autopilot, autopilot_caps, autopilot_ledger, spec_machine
from harness_maker.models import AtomicStage
from harness_maker.spec_machine import load_golden_table

_SPEC_YAML = Path(__file__).parents[2] / "specs/SPEC-ai-native-sdlc-vs-intent-world.machine.yaml"
_ROWS = load_golden_table(_SPEC_YAML, "AC-003")
_SLUG = "demo"
_PIPELINE = [
    AtomicStage.RESEARCH,
    AtomicStage.SPEC,
    AtomicStage.PLAN,
    AtomicStage.EXECUTE,
    AtomicStage.REVIEW,
    AtomicStage.VERIFY,
    AtomicStage.WRAPUP,
]
_DOC: dict[str, Any] = {
    "schema_version": 3,
    "spec_slug": _SLUG,
    "verification_tier": 1,
    "irreversible_decisions": [],
    "ac": [
        {
            "id": "AC-001",
            "title": "the thing works",
            "type": "mechanical",
            "executable_predicate": "result == 1",
            "oracle_source": "golden",
            "oracle_evidence": "hand-written",
            "pending_test": True,
        }
    ],
}


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    base = tmp_path / "repo"
    (base / "specs").mkdir(parents=True)
    for args in (["init", "-q"], ["config", "user.name", "Base User"]):
        subprocess.run(["git", *args], cwd=base, check=True, capture_output=True)
    return base


def _spec(root: Path, state: str) -> Path:
    yaml_path = root / "specs" / f"SPEC-{_SLUG}.machine.yaml"
    (root / "specs" / f"SPEC-{_SLUG}.md").write_text("---\ntype: spec\n---\n")
    doc = copy.deepcopy(_DOC)
    if state == "malformed":
        doc.pop("irreversible_decisions")
    yaml_path.write_text(yaml.safe_dump(doc, sort_keys=False))
    if state in ("approved", "invalid"):
        assert spec_machine.main(["approve", "--yaml", str(yaml_path)]) == 0
    if state == "exempt":
        assert spec_machine.main(["approve", "--yaml", str(yaml_path), "--exempt"]) == 0
    if state == "invalid":
        raw = yaml.safe_load(yaml_path.read_text())
        raw["ac"][0]["title"] = "edited after approval"
        yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    assert spec_machine.approval_state(root, _SLUG).state == state
    return yaml_path


def _boundary(root: Path, flag: str, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    capsys.readouterr()
    argv = ["boundary", "--root", str(root), "--current", "spec", "--slug", _SLUG]
    if flag != "absent":
        argv += ["--judgment-gate", flag]
    autopilot_caps.main(argv)
    out: dict[str, Any] = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return out


@pytest.mark.parametrize("row", _ROWS, ids=[r.note for r in _ROWS])
def test_ac_003_spec_boundary_table(
    root: Path, row: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    yaml_path = _spec(root, row.input["state"])
    had_approval = "approval" in yaml.safe_load(yaml_path.read_text())
    autopilot.write(root, level=row.input["level"], pipeline=list(_PIPELINE))
    got = _boundary(root, row.input["caller_flag"], capsys)
    expected = row.expected
    assert got["proceed"] is expected["proceed"]
    if "halt_kind" in expected:
        assert got["halt_kind"] == expected["halt_kind"]
    if expected.get("halt_kind") == "judgment_gate":
        # S3: "marker preserved" — a judgment halt is resumable, never terminal.
        assert autopilot.load(root, session_id=None) is not None
    if "ledger_event" in expected:
        assert autopilot_ledger.count_events(root, expected["ledger_event"]) == 1
    if expected.get("approval_written") is False:
        assert ("approval" in yaml.safe_load(yaml_path.read_text())) == had_approval


def test_ac_003_no_slug_derives_pending(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _spec(root, "approved")
    autopilot.write(root, level="auto_safe", pipeline=list(_PIPELINE))
    capsys.readouterr()
    autopilot_caps.main(
        ["boundary", "--root", str(root), "--current", "spec", "--judgment-gate", "clear"]
    )
    got = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert got["proceed"] is False
    assert got["halt_kind"] == "judgment_gate"
