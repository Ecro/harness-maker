"""SPEC-mark-tested-scope: mark-tested binds by name only within the task's changed test files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker import check, spec_machine
from tests.unit.test_hm_cost_p4_binding import _git, _spec, _write_tests

_GOLDEN_PATH = Path(__file__).resolve().parents[2] / "specs" / "SPEC-mark-tested-scope.golden.json"
_GOLDEN: dict[str, list[dict[str, Any]]] = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
_ROWS = [pytest.param(row, id=f"AC-001-{i}") for i, row in enumerate(_GOLDEN["AC-001"])]
_S1 = _GOLDEN["AC-001"][0]
_S2 = _GOLDEN["AC-001"][1]


def _tree(root: Path, inp: dict[str, Any]) -> tuple[Path, Path]:
    parametric = frozenset({"AC-001"}) if inp.get("parametric") else frozenset()
    yaml_path, md_path = _spec(root, ["AC-001"], parametric=parametric)
    if inp["git"]:
        _write_tests(root, inp.get("committed", []))
        _git(root, "init", "-q")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "base")
    for key in ("modified", "staged"):
        for nid in inp.get(key, []):
            file = nid.partition("::")[0]
            kept = [n for n in inp.get("committed", []) if n.startswith(f"{file}::")]
            _write_tests(root, [*kept, nid])
            if key == "staged":
                _git(root, "add", file)
    untracked = inp.get("untracked", [])
    reader = inp.get("reads_golden")
    _write_tests(root, [n for n in untracked if not n.startswith(f"{reader}::")])
    if reader:
        names = [n.partition("::")[2] for n in untracked if n.startswith(f"{reader}::")]
        body = "".join(f"def {n}():\n    assert 'SPEC-demo.golden.json'\n\n" for n in names)
        (root / reader).write_text(body, encoding="utf-8")
    return yaml_path, md_path


def _bind(root: Path, inp: dict[str, Any]) -> tuple[list[str], list[str], bool]:
    yaml_path, md_path = _tree(root, inp)
    before = yaml_path.read_bytes()
    errors = spec_machine.mark_tested(
        yaml_path, md_path, {"AC-001": list(inp.get("test_ids", []))}, validate_after=False
    )
    ac = spec_machine.load(yaml_path).ac[0]
    return sorted(ac.test_ids), errors, yaml_path.read_bytes() == before


@pytest.mark.parametrize("row", _ROWS)
def test_ac_001_binding_scope(tmp_path: Path, row: dict[str, Any]) -> None:
    bound, errors, untouched = _bind(tmp_path, row["input"])
    exp = row["expected"]
    if exp.get("refused"):
        assert len(errors) == 1, errors
        assert untouched
        assert bound == []
    else:
        assert errors == []
        assert bound == sorted(exp["bound"])


@pytest.mark.parametrize(
    "row",
    [
        pytest.param(r, id=f"row-{i}")
        for i, r in enumerate(_GOLDEN["AC-001"])
        if not r["input"].get("test_ids")
    ],
)
def test_ac_002_bind_equals_red_discovery(tmp_path: Path, row: dict[str, Any]) -> None:
    inp = row["input"]
    yaml_path, md_path = _tree(tmp_path, inp)
    spec = check.SpecView(spec_machine.load(yaml_path), yaml_path)
    red = check.red_discovery(tmp_path, spec, spec_machine.collect_runner(tmp_path))
    spec_machine.mark_tested(yaml_path, md_path, {"AC-001": []}, validate_after=False)
    bound = spec_machine.load(yaml_path).ac[0].test_ids
    assert sorted(bound) == sorted(red.get("AC-001", []))


def test_ac_003_no_repo_wide_collect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raises(_cwd: Path) -> tuple[list[str], bool]:
        raise AssertionError("repo-wide collect on the bind path")

    monkeypatch.setattr(spec_machine, "_pytest_collect_nodeids", _raises)
    s1 = tmp_path / "s1"
    s1.mkdir()
    bound, errors, _ = _bind(s1, _S1["input"])
    assert errors == []
    assert bound == _S1["expected"]["bound"]

    s2 = tmp_path / "s2"
    s2.mkdir()
    bound, errors, untouched = _bind(s2, _S2["input"])
    assert len(errors) == 1, errors
    for word in ("AC-001", "test_ac_001", "changed test files", "--test-id"):
        assert word in errors[0], (word, errors[0])
    assert untouched
    assert bound == []
