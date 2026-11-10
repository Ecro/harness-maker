"""SPEC-hm-cost-p4 AC-001..AC-003: AC tests use the gate's runner and are found by name."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from harness_maker import check, spec_machine

_SPEC = Path(__file__).resolve().parents[2] / "specs"
_GOLDEN: dict[str, list[dict[str, Any]]] = json.loads(
    (_SPEC / "SPEC-hm-cost-p4.golden.json").read_text(encoding="utf-8")
)
_SLUG = "demo"


def _cases(ac: str) -> list[Any]:
    return [pytest.param(row, id=f"{ac}-{i}") for i, row in enumerate(_GOLDEN[ac])]


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "maintenance.auto=false",
         "-c", "gc.auto=0", *args],
        cwd=root, check=True, capture_output=True, timeout=60,
    )  # fmt: skip


def _spec(
    root: Path, acs: list[str], *, pending: bool = True, parametric: frozenset[str] = frozenset()
) -> tuple[Path, Path]:
    specs = root / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    yaml_path = specs / f"SPEC-{_SLUG}.machine.yaml"
    md_path = specs / f"SPEC-{_SLUG}.md"
    lines = ["schema_version: 3", f"spec_slug: {_SLUG}", "verification_tier: 1", "ac:"]
    md = ["---", "type: spec", f"task_slug: {_SLUG}", "---", "", "## Acceptance Criteria", ""]
    for ac in acs:
        shape = (
            ["  type: parametric", "  golden_table: [{input: {n: 1}, expected: 1}]"]
            if ac in parametric
            else ["  type: mechanical", "  executable_predicate: 'True'"]
        )
        lines += [
            f"- id: {ac}", f"  title: behaviour {ac}", *shape, "  test_ids: []",
            f"  pending_test: {str(pending).lower()}",
            "  oracle_source: golden", "  oracle_evidence: fixed by the test",
        ]  # fmt: skip
        md += [f"### {ac}: behaviour {ac}", "x", ""]
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return yaml_path, md_path


def _write_tests(root: Path, nodeids: list[str], body: str = "assert True") -> None:
    by_file: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for nid in nodeids:
        file, _, rest = nid.partition("::")
        fn, _, case = rest.partition("[")
        by_file[file].setdefault(fn, [])
        if case:
            by_file[file][fn].append(case.rstrip("]"))
    for file, fns in by_file.items():
        out = ["import pytest", ""]
        for fn, cases in fns.items():
            if cases:
                out.append(f"@pytest.mark.parametrize('case', {cases!r})")
                out.append(f"def {fn}(case):\n    {body}\n")
            else:
                out.append(f"def {fn}():\n    {body}\n")
        path = root / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _venv_python(root: Path) -> None:
    """A `.venv/bin/python` that is this interpreter, so the gate's runner is `-m pytest` here."""
    py = root / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text(
        f"#!{sys.executable}\nimport os, sys\n"
        f"os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    py.chmod(0o755)


def test_ac_001_collect_with_gate_runner(tmp_path: Path) -> None:
    root = tmp_path
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("def x() -> int:\n    return 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_pkg.py").write_text(
        "from pkg import x\n\n\ndef test_ac_001_x():\n    assert x() == 1\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0"\n', encoding="utf-8"
    )
    _venv_python(root)
    yaml_path, md_path = _spec(root, ["AC-001"])
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    path_pytest = subprocess.run(
        ["pytest", "--collect-only", "-q", "tests"], cwd=root, env=env,
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    assert path_pytest.returncode != 0, "fixture must reproduce the PATH-pytest ImportError"
    venv = subprocess.run(
        [str(root / ".venv/bin/python"), "-m", "pytest", "--collect-only", "-q", "tests"],
        cwd=root, env=env, capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    assert venv.returncode == 0, venv.stdout + venv.stderr

    errors = spec_machine.mark_tested(yaml_path, md_path, {"AC-001": []})

    assert errors == []
    ac = spec_machine.load(yaml_path).ac[0]
    assert ac.test_ids == ["tests/test_pkg.py::test_ac_001_x"]
    assert ac.pending_test is False


@pytest.mark.parametrize("row", _cases("AC-002"))
def test_mark_tested_binding(tmp_path: Path, row: dict[str, Any]) -> None:
    inp, exp = row["input"], row["expected"]
    acs = sorted({*inp["acs"], *inp.get("pending", []), "AC-001", "AC-002", "AC-003"})
    yaml_path, md_path = _spec(tmp_path, acs)
    _write_tests(tmp_path, inp["tests"])
    if inp.get("find_unbound"):
        unbound = spec_machine.find_unbound_closed_type_acs(yaml_path, tmp_path)
        assert [a for a in unbound if a in inp["pending"]] == exp["unbound"]
        return
    before = yaml_path.read_bytes()
    errors = spec_machine.mark_tested(yaml_path, md_path, {a: [] for a in inp["acs"]})
    assert len(errors) == exp["errors"], errors
    for word in exp.get("error_mentions", []):
        assert any(word in e for e in errors), (word, errors)
    if exp["errors"]:
        assert yaml_path.read_bytes() == before
    model = {ac.id: ac for ac in spec_machine.load(yaml_path).ac}
    for ac_id, ids in exp["recorded"].items():
        assert sorted(model[ac_id].test_ids) == sorted(ids)


def _red_project(root: Path, inp: dict[str, Any]) -> Path:
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0"\n', encoding="utf-8"
    )
    _venv_python(root)
    pending = inp.get("pending_test", True)
    yaml_path, _ = _spec(
        root, ["AC-001", "AC-002"], pending=pending, parametric=frozenset({"AC-002"})
    )
    golden = yaml_path.with_name(f"SPEC-{_SLUG}.golden.json")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    plain = [t for t in inp["tests"] if " reading " not in t]
    reads = [t.split(" reading ")[0] for t in inp["tests"] if " reading " in t]
    code = inp["code"]
    if code == "absent_in_body":
        _write_tests(root, plain, "import pkg\n    assert pkg.VALUE == 2")
    elif code == "present":
        _write_tests(root, plain, "import pkg\n    assert pkg.VALUE == 1")
    else:  # module-level import of a name pkg does not define yet
        _write_tests(root, plain)
        for t in plain:
            path = root / t.partition("::")[0]
            path.write_text("from pkg import NEW\n" + path.read_text(encoding="utf-8"), "utf-8")
        for t in reads:
            file, _, fn = t.partition("::")
            (root / file).write_text(
                f"import json\nfrom pkg import NEW\n\nROWS = json.load(open('{golden}'))\n\n\n"
                f"def {fn}():\n    assert NEW\n",
                encoding="utf-8",
            )
    return yaml_path


@pytest.mark.parametrize("row", _cases("AC-003"))
def test_red_binding(tmp_path: Path, row: dict[str, Any]) -> None:
    inp, exp = row["input"], row["expected"]
    yaml_path = _red_project(tmp_path, inp)
    before = yaml_path.read_bytes()
    spec = check.load_spec(tmp_path, _SLUG)
    runner = check.pytest_runner(tmp_path, [])
    if inp["mode"] == "red":
        section = check.red_section(tmp_path, spec, runner, set(), "approved")
        assert section.code == exp["exit"], section.body
        assert sorted(section.body.get("not_red", {})) == exp["not_red"]
    else:
        section = check.ac_section(
            tmp_path, spec, "approved", check.changed_paths(tmp_path), runner
        )
        assert section.code == exp["exit"], section.body
        assert section.body["failed"] == exp["failed"]
    assert yaml_path.read_bytes() == before


def test_static_fallback_names_only_test_functions() -> None:
    """An uncollectable file's `test_cases = [...]` or `import testlib` is not a test to run."""
    source = (
        "import testlib\nfrom pkg import NEW\n\ntest_cases = [1]\n\n\n"
        "def test_a():\n    pass\n\n\ndef helper():\n    pass\n\n\n"
        "class TestB:\n    test_data = 1\n\n    def test_c(self):\n        pass\n\n"
        "    def setup(self):\n        pass\n"
    )
    assert check._static_test_names(source) == ["TestB::test_c", "test_a"]
    assert check._static_test_names("def broken(:\n") == []
