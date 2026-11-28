"""SPEC-readable-golden-rows: inline golden rows read like ordinary pytest parameters.

On 0.67.0 the Opus pairwise judge ruled hm's tests less maintainable than plain + "write tests"
3-29 and out of scope 0-30. The reasons named the rows' "Do not edit; hm check" header (35/36
pairs) and the adapter code `(input_dict, expected)` rows pull in (`f(**kwargs)`, string
stand-ins for exceptions). These tests pin the flat rows, the header-light block, the check that
still catches drift, and the stage sentences that keep the test shape plain.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any

from harness_maker import check, spec_machine
from tests.hm_cost_p2_fixture import init_project, param_ac, write_spec
from tests.unit.test_hm_cost_p2_templates import _render

FLAT_ROWS: list[dict[str, Any]] = [
    {"input": {"seconds": 5430, "max_units": 1}, "expected": "2h"},
    {"input": {"seconds": 3601, "max_units": 2}, "expected": "1h"},
]
MIXED_ROWS: list[dict[str, Any]] = [
    {"input": {"seconds": 0}, "expected": "0s"},
    {"input": {"seconds": 45, "max_units": 1}, "expected": "45s"},
]
FLAT_TEXT = (
    "# (seconds, max_units, expected)\n"
    "AC_001_ROWS = [\n"
    "    (5430, 1, '2h'),\n"
    "    (3601, 2, '1h'),\n"
    "]\n"
)
PAIR_TEXT = (
    "# (input, expected)\n"
    "AC_002_ROWS = [\n"
    "    ({'seconds': 0}, '0s'),\n"
    "    ({'seconds': 45, 'max_units': 1}, '45s'),\n"
    "]\n"
)
OLD_BLOCK = (
    "# AC-001 golden rows from SPEC-demo.machine.yaml: (input, expected).\n"
    "# Do not edit; `hm check` compares them with the SPEC.\n"
    "AC_001_ROWS = [\n"
    "    ({'seconds': 5430, 'max_units': 1}, '2h'),\n"
    "]\n"
)
NODE = "tests/test_fmt.py::test_ac_001_fmt"
EXECUTE_PHRASES = (
    "Add each test to its module's existing test file (a new file only for a new module).",
    "parametrize by its columns and call the code plainly (no `eval`, `getattr` or stand-ins)",
)
SPEC_PHRASES = (
    "A raising case is a mechanical AC (`pytest.raises`), not a golden row.",
    "A behaviour-unchanged AC covers only what no existing test asserts",
)


def test_ac_001_inline_rows_print_flat_under_a_column_header() -> None:
    flat = spec_machine.golden_inline_text({"AC-001": FLAT_ROWS})
    mixed = spec_machine.golden_inline_text({"AC-002": MIXED_ROWS})
    assert flat == FLAT_TEXT
    assert mixed == PAIR_TEXT
    for word in ("Do not edit", "hm check", "SPEC-"):
        assert word not in flat + mixed
    value = ast.literal_eval(flat.split(" = ", 1)[1])
    assert value == [(5430, 1, "2h"), (3601, 2, "1h")]


def test_ac_001_pair_form_for_rows_that_cannot_flatten() -> None:
    for rows in (
        [{"input": "1h", "expected": 3600}],
        [{"input": {"not-an-id": 1}, "expected": 1}],
        [{"input": {"expected": 1}, "expected": 1}],
        [{"input": {"class": 1}, "expected": 1}],
        [{"input": {}, "expected": 1}],
        [{"input": {"a": 1, "b": 2}, "expected": 1}, {"input": {"b": 2, "a": 1}, "expected": 1}],
    ):
        text = spec_machine.golden_inline_text({"AC-001": rows})
        assert text.startswith("# (input, expected)\n"), text
        want = [(r["input"], r["expected"]) for r in rows]
        assert ast.literal_eval(text.split(" = ", 1)[1]) == want


def test_ac_001_export_inline_cli_prints_flat_rows_and_writes_no_json(tmp_path: Path) -> None:
    """Moved from SPEC-inline-golden-rows AC-001, which this SPEC retires."""
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", [{"input": {"s": "1h"}, "expected": 3600}])])
    r = subprocess.run(
        [sys.executable, "-m", "harness_maker.spec_machine", "export-golden", "--inline",
         "--yaml", str(root / "specs" / "SPEC-demo.machine.yaml")],
        capture_output=True, text=True, check=False, timeout=60,
    )  # fmt: skip
    assert r.returncode == 0, r.stderr
    assert not (root / "specs" / "SPEC-demo.golden.json").exists()
    assert r.stdout == "# (s, expected)\nAC_001_ROWS = [\n    ('1h', 3600),\n]\n"


def test_ac_002_write_replaces_old_and_new_blocks_in_place(tmp_path: Path) -> None:
    head, tail = "import pytest\n\n", "\n\ndef test_ac_001_fmt():\n    assert True\n"
    target = tmp_path / "test_fmt.py"
    # A 0.67.0 block keeps its pair form, since its test unpacks dicts; only the header changes.
    target.write_text(head + OLD_BLOCK + tail, encoding="utf-8")
    assert spec_machine.write_inline_rows(target, {"AC-001": FLAT_ROWS})
    pairs = spec_machine.golden_inline_text({"AC-001": FLAT_ROWS}, flat=False)
    assert pairs.startswith("# (input, expected)\nAC_001_ROWS = [\n    ({'seconds': 5430")
    assert target.read_text(encoding="utf-8") == head + pairs + tail

    # A flat block is replaced in place and stays flat; a user comment above it survives.
    target.write_text(head + "# (see issue 42)\n" + FLAT_TEXT + tail, encoding="utf-8")
    changed = [dict(FLAT_ROWS[0], expected="3h"), FLAT_ROWS[1]]
    assert spec_machine.write_inline_rows(target, {"AC-001": changed})
    text = target.read_text(encoding="utf-8")
    assert text.count("AC_001_ROWS =") == 1
    assert text == head + "# (see issue 42)\n" + FLAT_TEXT.replace("'2h'", "'3h'") + tail
    assert not spec_machine.write_inline_rows(target, {"AC-001": changed})


def test_ac_002_write_refuses_another_specs_rows(tmp_path: Path) -> None:
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", FLAT_ROWS, test_ids=[NODE], pending_test=False)], slug="a")
    write_spec(root, [param_ac("AC-001", MIXED_ROWS)], slug="b")
    target = root / "tests" / "test_fmt.py"
    target.parent.mkdir()
    target.write_text(FLAT_TEXT, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-m", "harness_maker.spec_machine", "export-golden", "--inline",
         "--write", "tests/test_fmt.py", "--slug", "b"],
        cwd=root, capture_output=True, text=True, check=False, timeout=60,
    )  # fmt: skip
    assert r.returncode == 1, r.stdout + r.stderr
    assert "SPEC-a.machine.yaml AC-001" in r.stderr
    assert target.read_text(encoding="utf-8") == FLAT_TEXT


def _project(tmp_path: Path, literal: str) -> Path:
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", FLAT_ROWS, test_ids=[NODE], pending_test=False)])
    (root / "tests").mkdir()
    (root / "tests" / "test_fmt.py").write_text(
        f"# (seconds, max_units, expected)\nAC_001_ROWS = {literal}\n\n\n"
        "def test_ac_001_fmt():\n    assert True\n",
        encoding="utf-8",
    )
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    wrapper = venv_bin / "python"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    wrapper.chmod(0o755)
    return root


def _drift(tmp_path: Path, literal: str) -> tuple[Any, list[str]]:
    root = _project(tmp_path, literal)
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    return ac.get("golden"), ac.get("golden_drift", {}).get("acs", [])


def test_ac_003_check_accepts_flat_rows_and_still_catches_drift(tmp_path: Path) -> None:
    assert _drift(tmp_path / "a", "[(5430, 1, '2h'), (3601, 2, '1h')]") == ("inline", [])
    pairs = "[({'seconds': 5430, 'max_units': 1}, '2h'), ({'seconds': 3601, 'max_units': 2}, '1h')]"
    assert _drift(tmp_path / "b", pairs) == ("inline", [])
    assert _drift(tmp_path / "c", "[(5430, 1, '2h'), (3601, 2, '9h')]") == ("inline", ["AC-001"])
    assert _drift(tmp_path / "d", "[(5430, 1, '2h')]") == ("inline", ["AC-001"])
    assert _drift(tmp_path / "e", "[(5430, '2h'), (3601, '1h')]") == ("inline", ["AC-001"])


def test_ac_003_flat_rows_need_todays_column_header(tmp_path: Path) -> None:
    """Flat rows are positional: a renamed SPEC key keeps the values but not the header."""
    root = _project(tmp_path, "[(5430, 1, '2h'), (3601, 2, '1h')]")
    test = root / "tests" / "test_fmt.py"
    test.write_text(FLAT_TEXT + "\n\ndef test_ac_001_fmt():\n    assert True\n", encoding="utf-8")
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    assert ac.get("golden_drift", {}).get("acs", []) == []
    test.write_text(
        test.read_text(encoding="utf-8").replace("max_units", "units"), encoding="utf-8"
    )
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    assert ac.get("golden_drift", {}).get("acs", []) == ["AC-001"]


def test_ac_004_execute_asks_for_placement_unpacked_rows_and_plain_calls() -> None:
    for is_codex in (False, True):
        text = _render("execute", is_codex=is_codex)
        for phrase in EXECUTE_PHRASES:
            assert phrase in text, phrase


def test_ac_005_spec_keeps_raising_and_already_tested_cases_out_of_golden_rows() -> None:
    for is_codex in (False, True):
        text = _render("spec", is_codex=is_codex)
        for phrase in SPEC_PHRASES:
            assert phrase in text, phrase
