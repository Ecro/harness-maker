"""SPEC-inline-golden-rows: golden rows live in the test file, and `hm check` compares them.

Tests that read `SPEC-<slug>.golden.json` lost the 2026-11-25 pairwise maintainability judgement
0-33: a reader saw neither inputs nor expectations. Rows pasted as an `AC_NNN_ROWS` literal keep
the oracle visible; the comparison keeps the "never regenerate golden rows" guarantee.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_maker import check
from tests.hm_cost_p2_fixture import init_project, param_ac, write_golden, write_spec
from tests.unit.test_hm_cost_p2_templates import _render

ROWS: list[dict[str, Any]] = [
    {"input": {"s": "1h"}, "expected": 3600, "note": "hour"},
    {"input": {"s": "bad"}, "expected": "ValueError"},
]
WANT = [({"s": "1h"}, 3600), ({"s": "bad"}, "ValueError")]
NODE = "tests/test_parse.py::test_ac_001_parse"


def _export(root: Path) -> subprocess.CompletedProcess[str]:
    yaml_path = root / "specs" / "SPEC-demo.machine.yaml"
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.spec_machine", "export-golden", "--inline",
         "--yaml", str(yaml_path)],
        capture_output=True, text=True, check=False, timeout=60,
    )  # fmt: skip


def test_ac_001_export_golden_inline_prints_literal_rows(tmp_path: Path) -> None:
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", ROWS)])
    r = _export(root)
    assert r.returncode == 0, r.stderr
    assert not (root / "specs" / "SPEC-demo.golden.json").exists()
    tree = ast.parse(r.stdout)
    assigns = {
        n.targets[0].id: ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
    }
    assert assigns == {"AC_001_ROWS": WANT}


def _project(tmp_path: Path, rows_literal: str | None) -> Path:
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", ROWS, test_ids=[NODE], pending_test=False)])
    (root / "tests").mkdir()
    head = f"AC_001_ROWS = {rows_literal}\n\n\n" if rows_literal is not None else ""
    (root / "tests" / "test_parse.py").write_text(
        f"{head}def test_ac_001_parse():\n    assert True\n", encoding="utf-8"
    )
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    wrapper = venv_bin / "python"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    wrapper.chmod(0o755)
    return root


@pytest.mark.parametrize(
    ("rows_literal", "golden", "drift"),
    [
        (repr(WANT), "inline", []),
        ("[({'s': '1h'}, 3601), ({'s': 'bad'}, 'ValueError')]", "inline", ["AC-001"]),
        ("[({'s': '1h'}, 3600)]", "inline", ["AC-001"]),
        (None, "absent", []),
    ],
    ids=["AC-002-0", "AC-002-1", "AC-002-2", "AC-002-3"],
)
def test_ac_002_hm_check_compares_inline_rows(
    tmp_path: Path, rows_literal: str | None, golden: str, drift: list[str]
) -> None:
    root = _project(tmp_path, rows_literal)
    result = check.run(check.Options(slug="demo", root=root, offline=True))
    ac = result["sections"]["ac"]
    assert ac.get("golden") == golden, ac
    assert ac.get("golden_drift", {}).get("acs", []) == drift, ac
    if drift:
        assert ac["ok"] is False
        assert result["exit"] == 1
        assert "--inline" in ac["golden_drift"]["fix"]
    else:
        assert ac["ok"] is True, ac


def test_ac_002_with_a_json_file_both_are_compared(tmp_path: Path) -> None:
    """An old SPEC re-run under the inline recipe holds both; rewriting the JSON alone must not
    pass while the pasted rows still drift."""
    root = _project(tmp_path, "[({'s': '1h'}, 3601), ({'s': 'bad'}, 'ValueError')]")
    write_golden(root, {"AC-001": [{"input": r["input"], "expected": r["expected"]} for r in ROWS]})
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    assert ac["golden"] == "present"
    assert ac["golden_drift"]["acs"] == ["AC-001"], ac


def test_ac_002_every_file_holding_the_rows_is_compared(tmp_path: Path) -> None:
    root = _project(tmp_path, repr(WANT))
    other = "tests/test_more.py::test_ac_001_more"
    write_spec(root, [param_ac("AC-001", ROWS, test_ids=[NODE, other], pending_test=False)])
    (root / "tests" / "test_more.py").write_text(
        "AC_001_ROWS = [({'s': '1h'}, 999)]\n\n\ndef test_ac_001_more():\n    assert True\n",
        encoding="utf-8",
    )
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    assert ac["golden_drift"]["acs"] == ["AC-001"], ac


@pytest.mark.parametrize(
    "rows_literal",
    ["[pytest.param({'s': '1h'}, 3600)]", "[(r, 1) for r in range(2)]"],
    ids=["call", "comprehension"],
)
def test_ac_002_rows_that_are_not_a_literal_are_drift(tmp_path: Path, rows_literal: str) -> None:
    root = _project(tmp_path, rows_literal)
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    assert ac["golden_drift"]["acs"] == ["AC-001"], ac


def test_ac_002_a_sibling_without_rows_is_drift(tmp_path: Path) -> None:
    """Once one AC shows its rows, an AC whose test shows none reads its oracle from somewhere
    `hm check` cannot see."""
    root = _project(tmp_path, repr(WANT))
    node_2 = "tests/test_other.py::test_ac_002_other"
    write_spec(
        root,
        [
            param_ac("AC-001", ROWS, test_ids=[NODE], pending_test=False),
            param_ac("AC-002", ROWS, test_ids=[node_2], pending_test=False),
        ],
    )
    (root / "tests" / "test_other.py").write_text(
        "def test_ac_002_other():\n    assert True\n", encoding="utf-8"
    )
    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    assert ac["golden"] == "inline"
    assert ac["golden_drift"]["acs"] == ["AC-002"], ac


def test_ac_003_execute_pastes_inline_rows() -> None:
    text = _render("execute")
    assert "export-golden --inline" in text
    assert "`AC_NNN_ROWS`" in text
    assert "golden.json" not in text


def test_ac_004_spec_verification_names_acs_not_tests() -> None:
    text = _render("spec")
    assert "Verification (scenario, mode, AC)" in text
    assert "Verification (scenario, mode, test)" not in text
