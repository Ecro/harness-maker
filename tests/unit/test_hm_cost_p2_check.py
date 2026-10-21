"""SPEC-hm-cost-p2 AC-002 (golden JSON vs machine.yaml) and AC-006 (compact `hm check` output)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_maker import check
from harness_maker.spec_machine import load_golden_table
from tests._overhaul_p1_ref import clean_env, ref_root
from tests.hm_cost_p2_fixture import init_project, mech_ac, param_ac, write_golden, write_spec

SPEC_YAML = Path(__file__).parents[2] / "specs" / "SPEC-hm-cost-p2.machine.yaml"
REF_SHA = "473ac3f1"

ROWS_1 = [{"input": {"s": "1h"}, "expected": 3600, "note": "hour"}]
ROWS_2 = [{"input": {"s": "2m"}, "expected": 120}]
# The JSON each variant starts from, written by hand as the `{input, expected}` projection.
MATCHING = {
    "AC-001": [{"input": {"s": "1h"}, "expected": 3600}],
    "AC-002": [{"input": {"s": "2m"}, "expected": 120}],
}


def _build(root: Path, variant: str) -> None:
    rows_1 = [dict(r) for r in ROWS_1]
    if variant == "row_drift_ac_001":
        rows_1[0]["expected"] = 3601
    if variant == "note_only_edit":
        rows_1[0]["note"] = "an hour, edited"
    write_spec(root, [param_ac("AC-001", rows_1), param_ac("AC-002", ROWS_2)])
    if variant == "absent":
        return
    payload = dict(MATCHING)
    if variant == "missing_ac_002":
        del payload["AC-002"]
    write_golden(root, payload)


def _row_id(row: Any) -> str:
    return "-".join(map(str, row.input.values()))


@pytest.mark.parametrize("row", load_golden_table(SPEC_YAML, "AC-002"), ids=_row_id)
def test_ac_002_golden_comparison(tmp_path: Path, row: Any) -> None:
    root = init_project(tmp_path / "p")
    _build(root, row.input["json"])
    result = check.run(
        check.Options(slug="demo", root=root, red=row.input["mode"] == "red", offline=True)
    )
    ac = result["sections"]["ac"]
    drift = ac.get("golden_drift", {})
    observed = {
        "ac_failed_by_golden": sorted(drift.get("acs", [])),
        "golden": ac.get("golden"),
        "hint": "export-golden" in str(ac.get("hint", "")),
    }
    assert observed == row.expected
    if observed["ac_failed_by_golden"]:
        assert ac["ok"] is False
        assert result["exit"] != 0
        assert "export-golden" in drift["fix"]


def _venv(root: Path) -> None:
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    wrapper = venv_bin / "python"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    wrapper.chmod(0o755)


@pytest.mark.parametrize("red", [False, True], ids=["check", "red"])
def test_ac_002_drift_alone_fails_a_passing_section(tmp_path: Path, red: bool) -> None:
    """The same project exits 0 with a matching JSON and 1 with a drifted one, so the failure
    is the drift's and not a pending AC's or a missing runner's."""
    root = init_project(tmp_path / "p")
    node = "tests/test_golden.py::test_golden"
    write_spec(root, [param_ac("AC-001", ROWS_1, pending_test=red, test_ids=[node])])
    got = "None  # RED: the parser is not written yet" if red else "3600"
    (root / "tests").mkdir()
    (root / "tests" / "test_golden.py").write_text(
        f"def test_golden():\n    assert {got} == 3600\n", encoding="utf-8"
    )
    _venv(root)
    opts = check.Options(slug="demo", root=root, red=red, offline=True)

    write_golden(root, {"AC-001": MATCHING["AC-001"]})
    clean = check.run(opts)
    assert clean["sections"]["ac"]["ok"] is True, clean["sections"]["ac"]
    assert clean["exit"] == 0, clean

    write_golden(root, {"AC-001": [{"input": {"s": "1h"}, "expected": 3601}]})
    drifted = check.run(opts)
    assert drifted["sections"]["ac"]["golden_drift"]["acs"] == ["AC-001"]
    assert drifted["sections"]["ac"]["ok"] is False
    assert drifted["exit"] == 1, drifted


def test_ac_002_absent_names_an_unexportable_row(tmp_path: Path) -> None:
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", [{"input": {"s": "x"}, "expected": {1: "one"}}])])
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    assert ac["golden"] == "absent"
    assert "AC-001" in ac["hint"]
    assert "refuses" in ac["hint"]

    write_golden(root, MATCHING)
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    assert ac["ok"] is False
    assert len(ac["golden_drift"]["acs"]) == 1
    assert ac["golden_drift"]["acs"][0].startswith("AC-001: row 0")


# ── AC-006 ──────────────────────────────────────────────────────────────────

_EMPTY: tuple[Any, ...] = ("", [], {}, None)
REQUIRED_KEEP = {
    "pending", "notice", "skipped", "status", "reason", "waived", "green_before", "golden", "hint"
}  # fmt: skip


def compact(out: dict[str, Any], keep: set[str]) -> dict[str, Any]:
    def reduce(body: dict[str, Any]) -> dict[str, Any]:
        if body.get("ok") is not True:
            return body
        return {"ok": True, **{k: v for k, v in body.items() if k in keep and v not in _EMPTY}}

    sections = {name: reduce(body) for name, body in out["sections"].items()}
    return {**out, "sections": sections}


def strip(out: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    sections = dict(out["sections"])
    ac = {k: v for k, v in sections.get("ac", {}).items() if f"ac.{k}" not in keys}
    sections["ac"] = ac
    return {**out, "sections": sections}


def _full_fixture(root: Path) -> list[str]:
    """Self-approved SPEC (no stamp at auto_full) and an offline CVE skip."""
    init_project(root)
    write_spec(root, [mech_ac("AC-001")])
    return ["--offline"]


def _red_fixture(root: Path) -> list[str]:
    """A waived RED AC: its test already passes and `--green-ok` names it."""
    init_project(root)
    write_spec(root, [mech_ac("AC-001", test_ids=["tests/test_ok.py::test_ok"])])
    (root / "tests").mkdir()
    (root / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    wrapper = venv_bin / "python"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    wrapper.chmod(0o755)
    return ["--red", "--green-ok", "AC-001"]


def _run(src: Path, home: Path, root: Path, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.check", "--slug", "demo", "--root", str(root), *args],
        env=clean_env(home=home, src=src), capture_output=True, text=True, timeout=300, check=False,
    )  # fmt: skip
    line = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")][-1]
    parsed: dict[str, Any] = json.loads(line)
    return parsed


@pytest.mark.parametrize("fixture", [_full_fixture, _red_fixture], ids=["full", "red"])
def test_ac_006_compact_output(tmp_path: Path, fixture: Any) -> None:
    root = tmp_path / "p"
    args = fixture(root)
    home = tmp_path / "home"
    home.mkdir()
    head_src = Path(check.__file__).resolve().parents[1]
    pre_change_out = _run(ref_root(tmp_path / "ref", REF_SHA) / "src", home, root, args)
    full_out = _run(head_src, home, root, [*args, "--full"])
    default_out = _run(head_src, home, root, args)

    keep = set(check.COMPACT_KEEP)
    assert keep >= REQUIRED_KEEP
    assert default_out == compact(full_out, keep)
    assert strip(full_out, ("ac.golden", "ac.hint")) == pre_change_out
    # The fixtures exist to prove these survive compaction.
    sections = default_out["sections"]
    if "--red" in args:
        assert sections["ac"].get("waived") == ["AC-001"]
    else:
        assert sections["approval"].get("pending") is True
        assert sections["cve"].get("status") == "skipped"
