"""SPEC-behaviour-named-tests: tests named for behaviour, the AC link kept in the SPEC.

After SPEC-readable-golden-rows the evidence-citing pairwise judge still ruled hm's tests less
maintainable than plain + "write tests" 7-27. The decisive evidence was requirement-id names
(`AC_001_ROWS`, `test_ac_001_*`, ids `AC-001-i`) in 17 of 27 losses; renaming them by behaviour
plus repo-style double quotes turned two losses into a tie and an hm win, and one golden table per
function turned a string-dispatch loss into a split. These tests pin the binding that no longer
needs AC ids in names, the name-chosen row write, the quote style, the check that finds rows
through the bound test's own `parametrize`, and the stage sentences.
"""

from __future__ import annotations

import ast
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

from harness_maker import check, spec_machine
from tests.hm_cost_p2_fixture import init_project, mech_ac, param_ac, write_spec
from tests.unit.test_hm_cost_p2_templates import _render

FLAT_ROWS: list[dict[str, Any]] = [
    {"input": {"seconds": 5430, "max_units": 1}, "expected": "2h"},
    {"input": {"seconds": 3601, "max_units": 2}, "expected": "1h"},
]
OTHER_ROWS: list[dict[str, Any]] = [{"input": {"seconds": 0}, "expected": "0s"}]
NODE = "tests/test_fmt.py::test_max_units"
COLS = '("seconds", "max_units", "expected")'
TEST_BODY = "def test_max_units(seconds, max_units, expected):\n    assert False\n"
EXECUTE_PHRASES = (
    "No AC id goes in a test name, case id or constant",
    "--ac AC-NNN --name",
    "hm spec_machine bind --slug <slug> --test-id AC-NNN=<node id>",
    "never copy the implementation",
    "export-golden --inline",
)
SPEC_PHRASE = "A golden table maps one function's arguments to its return value"


def _venv(root: Path) -> None:
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    wrapper = venv_bin / "python"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    wrapper.chmod(0o755)


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.spec_machine", *args],
        cwd=root, capture_output=True, text=True, check=False, timeout=60,
    )  # fmt: skip


def _bind_project(tmp_path: Path) -> tuple[Path, Path]:
    root = init_project(tmp_path / "p")
    yaml_path = write_spec(root, [mech_ac("AC-001")])
    spec_machine.approve(yaml_path)
    (root / "tests").mkdir()
    (root / "tests" / "test_fmt.py").write_text(
        "def test_max_units():\n    assert False, 'not built yet'\n", encoding="utf-8"
    )
    _venv(root)
    return root, yaml_path


def test_bind_records_tests_before_red(tmp_path: Path) -> None:
    root, yaml_path = _bind_project(tmp_path)
    r = _cli(root, "bind", "--slug", "demo", "--test-id", f"AC-001={NODE}")
    assert r.returncode == 0, r.stdout + r.stderr
    ac = spec_machine.load(yaml_path).ac[0]
    assert ac.test_ids == [NODE]
    assert ac.pending_test is True
    assert spec_machine.approval_state_of("demo", yaml_path).state == "approved"
    red = check.run(check.Options(slug="demo", root=root, red=True, offline=True))
    section = red["sections"]["ac"]
    assert section["ok"] is True, section
    assert section["not_red"] == {}


def test_bind_refuses_missing_tests_and_unknown_acs(tmp_path: Path) -> None:
    root, yaml_path = _bind_project(tmp_path)
    before = yaml_path.read_bytes()
    for test_id in (
        "AC-001=tests/test_fmt.py::test_absent",
        "AC-001=tests/test_none.py::test_max_units",
        f"AC-009={NODE}",
    ):
        r = _cli(root, "bind", "--slug", "demo", "--test-id", test_id)
        assert r.returncode == 1, (test_id, r.stdout, r.stderr)
        assert yaml_path.read_bytes() == before


def _rows_project(tmp_path: Path) -> tuple[Path, Path]:
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", FLAT_ROWS), param_ac("AC-002", OTHER_ROWS)])
    target = root / "tests" / "test_format.py"
    target.parent.mkdir()
    target.write_text("import pytest\n\n\ndef test_x():\n    pass\n", encoding="utf-8")
    return root, target


def test_export_golden_writes_one_acs_rows_under_a_chosen_name(tmp_path: Path) -> None:
    root, target = _rows_project(tmp_path)
    write = ("export-golden", "--inline", "--write", "tests/test_format.py", "--slug", "demo")
    r = _cli(root, *write, "--ac", "AC-001", "--name", "MAX_UNITS_CASES")
    assert r.returncode == 0, r.stdout + r.stderr
    block = 'MAX_UNITS_CASES = [\n    (5430, 1, "2h"),\n    (3601, 2, "1h"),\n]\n'
    expected = "import pytest\n\n\n" + block + "\n\ndef test_x():\n    pass\n"
    assert target.read_text(encoding="utf-8") == expected
    # The same rows again: in place, unchanged.
    r = _cli(root, *write, "--ac", "AC-001", "--name", "MAX_UNITS_CASES")
    assert r.returncode == 0, r.stderr
    assert target.read_text(encoding="utf-8") == expected
    # Another AC's rows under a name that already holds different rows: refused, untouched.
    r = _cli(root, *write, "--ac", "AC-002", "--name", "MAX_UNITS_CASES")
    assert r.returncode == 1, r.stdout + r.stderr
    assert target.read_text(encoding="utf-8") == expected


def test_export_golden_name_needs_an_ac_and_an_identifier(tmp_path: Path) -> None:
    root, target = _rows_project(tmp_path)
    before = target.read_text(encoding="utf-8")
    write = ("export-golden", "--inline", "--write", "tests/test_format.py", "--slug", "demo")
    for extra in (("--name", "CASES"), ("--ac", "AC-001", "--name", "not-a-name")):
        r = _cli(root, *write, *extra)
        assert r.returncode == 2, (extra, r.stdout, r.stderr)
    assert target.read_text(encoding="utf-8") == before


_CHARS = "ab'\"\\\n\tz é 漢 \x00"


def _value(rng: random.Random, depth: int = 0) -> Any:
    kinds = ["str", "int", "float", "bool", "none"] + (
        ["list", "tuple", "dict"] if depth < 3 else []
    )
    kind = rng.choice(kinds)
    if kind == "str":
        return "".join(rng.choice(_CHARS) for _ in range(rng.randint(0, 6)))
    if kind == "int":
        return rng.randint(-(10**12), 10**12)
    if kind == "float":
        return rng.uniform(-1e6, 1e6)
    if kind == "bool":
        return rng.random() < 0.5
    if kind == "none":
        return None
    items = [_value(rng, depth + 1) for _ in range(rng.randint(0, 3))]
    if kind == "list":
        return items
    if kind == "tuple":
        return tuple(items)
    return {f"k{i}": v for i, v in enumerate(items)}


def test_printed_rows_read_back_exactly() -> None:
    rng = random.Random(20261128)
    for _ in range(2000):
        value = _value(rng)
        text = spec_machine.py_literal(value)
        assert ast.literal_eval(text) == value, text
        assert type(ast.literal_eval(text)) is type(value)
        if isinstance(value, str) and '"' not in value:
            assert text.startswith('"'), text
            assert text.endswith('"'), text


def _drift_project(tmp_path: Path, test_text: str) -> tuple[Any, list[str]]:
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", FLAT_ROWS, test_ids=[NODE], pending_test=False)])
    (root / "tests").mkdir()
    (root / "tests" / "test_fmt.py").write_text("import pytest\n\n" + test_text, encoding="utf-8")
    _venv(root)
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    return ac.get("golden"), ac.get("golden_drift", {}).get("acs", [])


ROWS = '[(5430, 1, "2h"), (3601, 2, "1h")]'


def test_check_finds_rows_through_the_bound_tests_parametrize(tmp_path: Path) -> None:
    variants = {
        "constant": f"CASES = {ROWS}\n\n\n@pytest.mark.parametrize({COLS}, CASES)\n{TEST_BODY}",
        "inline": f"@pytest.mark.parametrize({COLS}, {ROWS})\n{TEST_BODY}",
        "extended": (
            f'@pytest.mark.parametrize({COLS}, [(0, 1, "0s"), (5430, 1, "2h"), (3601, 2, "1h")])\n'
            f"{TEST_BODY}"
        ),
        "enumerate": (
            f"CASES = {ROWS}\n\n\n@pytest.mark.parametrize(\n    {COLS},\n"
            '    [pytest.param(*r, id=f"c{i}") for i, r in enumerate(CASES)],\n)\n'
            f"{TEST_BODY}"
        ),
        "keywords": (f"@pytest.mark.parametrize(argnames={COLS}, argvalues={ROWS})\n{TEST_BODY}"),
    }
    for name, text in variants.items():
        assert _drift_project(tmp_path / name, text) == ("inline", []), name


def test_check_names_the_ac_when_a_parametrized_row_changes(tmp_path: Path) -> None:
    edited = '[(5430, 1, "2h"), (3601, 2, "9h")]'
    missing = '[(5430, 1, "2h")]'
    for name, rows in (("edited", edited), ("missing", missing)):
        text = f"@pytest.mark.parametrize({COLS}, {rows})\n{TEST_BODY}"
        assert _drift_project(tmp_path / name, text) == ("inline", ["AC-001"]), name


def test_check_leaves_a_load_golden_table_test_to_the_legacy_verdict(tmp_path: Path) -> None:
    text = (
        "from harness_maker.spec_machine import load_golden_table\n\n"
        'ROWS = load_golden_table("specs/SPEC-demo.machine.yaml", "AC-001")\n\n\n'
        '@pytest.mark.parametrize("row", ROWS)\ndef test_max_units(row):\n    assert False\n'
    )
    golden, drift = _drift_project(tmp_path, text)
    assert golden == "absent"
    assert drift == []
    root = tmp_path / "p"
    spec = check.load_spec(root, "demo")
    assert spec is not None
    want = spec_machine.golden_export(spec.model)
    assert check._inline_golden_drift(root, spec, want) is None


def test_execute_names_tests_for_behaviour_and_binds_them() -> None:
    for is_codex in (False, True):
        text = _render("execute", is_codex=is_codex)
        for banned in (
            "test_ac_NNN", "AC-NNN-<i>", "AC_NNN_ROWS", "spec_machine validate", "golden.json",
            "Put each test's node id in its AC's `test_ids`",
        ):  # fmt: skip
            assert banned not in text, banned
        for phrase in EXECUTE_PHRASES:
            assert phrase in text, phrase
        assert text.index("spec_machine bind --slug") < text.index("**RED**")


def test_spec_keeps_a_golden_table_to_one_call_shape() -> None:
    for is_codex in (False, True):
        assert SPEC_PHRASE in _render("spec", is_codex=is_codex)


def test_bind_again_replaces_a_renamed_test_and_refuses_non_tests(tmp_path: Path) -> None:
    """REVIEW F1/F9: a test renamed after the first bind is fixed by binding again."""
    root, yaml_path = _bind_project(tmp_path)
    assert _cli(root, "bind", "--slug", "demo", "--test-id", f"AC-001={NODE}").returncode == 0
    test = root / "tests" / "test_fmt.py"
    test.write_text("CASES = [1]\n\n\ndef test_renamed():\n    assert False\n", encoding="utf-8")
    renamed = "tests/test_fmt.py::test_renamed"
    assert _cli(root, "bind", "--slug", "demo", "--test-id", f"AC-001={renamed}").returncode == 0
    assert spec_machine.load(yaml_path).ac[0].test_ids == [renamed]
    outside = tmp_path / "outside.py"
    outside.write_text("def test_o():\n    assert False\n", encoding="utf-8")
    for bad in ("tests/test_fmt.py::CASES", "../outside.py::test_o"):
        r = _cli(root, "bind", "--slug", "demo", "--test-id", f"AC-001={bad}")
        assert r.returncode == 1, (bad, r.stdout, r.stderr)


def test_export_golden_never_shadows_or_crashes_on_an_existing_name(tmp_path: Path) -> None:
    """REVIEW F6/F7/F8."""
    root, target = _rows_project(tmp_path)
    write = ("export-golden", "--inline", "--write", "tests/test_format.py", "--slug", "demo")
    for existing in ("CASES = [1, 2]\n", 'CASES = [(5430, 1, "2h")]  # one line\n'):
        target.write_text("import pytest\n\n" + existing, encoding="utf-8")
        r = _cli(root, *write, "--ac", "AC-001", "--name", "CASES")
        assert r.returncode == 1, (existing, r.stdout, r.stderr)
        assert target.read_text(encoding="utf-8") == "import pytest\n\n" + existing
    write_spec(root, [mech_ac("AC-001")])
    r = _cli(root, *write, "--ac", "AC-001", "--name", "OTHER")
    assert r.returncode == 1, r.stdout + r.stderr


def test_check_reads_only_cases_the_test_really_runs(tmp_path: Path) -> None:
    """REVIEW F2/F3/F5: `+` of two lists resolves; a filtering or mapping comprehension and an
    unreadable shape drift instead of passing as `absent`; `True` is not the row `1`."""
    consts = f'BASE = [(0, 1, "0s")]\nCASES = {ROWS}\n\n\n'
    joined = f"{consts}@pytest.mark.parametrize({COLS}, BASE + CASES)\n"
    assert _drift_project(tmp_path / "join", joined + TEST_BODY) == ("inline", [])
    for name, cases in (
        ("filtered", "[r for r in CASES if r[1] > 1]"),
        ("mapped", "[(a, b, c * 2) for a, b, c in CASES]"),
        ("computed", "make_cases()"),
        ("bool", '[(5430, True, "2h"), (3601, 2, "1h")]'),
    ):
        text = f"{consts}@pytest.mark.parametrize({COLS}, {cases})\n{TEST_BODY}"
        assert _drift_project(tmp_path / name, text) == ("inline", ["AC-001"]), name
