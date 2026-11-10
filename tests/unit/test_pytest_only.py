"""SPEC-pytest-only: the no-runner reason names the pytest-only limit on a non-Python project."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import check
from tests.hm_cost_p2_fixture import init_project, mech_ac, write_spec

LIMIT = "the RED and AC gates run pytest only"
MARKERS = (
    "pyproject.toml", "setup.py", "setup.cfg", "tox.ini", "pytest.ini", "conftest.py",
    "Pipfile", "poetry.lock", "uv.lock", "requirements.txt", "requirements-dev.txt",
)  # fmt: skip


@pytest.mark.parametrize("marker", [None, "package.json", "Cargo.toml", "go.mod"])
def test_ac_001_non_python_root_names_the_limit(tmp_path: Path, marker: str | None) -> None:
    if marker:
        (tmp_path / marker).write_text("{}\n", encoding="utf-8")
    assert LIMIT in check.no_runner_reason(tmp_path)


@pytest.mark.parametrize("where", ["", "backend/"])
@pytest.mark.parametrize("marker", MARKERS)
def test_ac_001_python_root_keeps_its_reason(tmp_path: Path, marker: str, where: str) -> None:
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / where).mkdir(exist_ok=True)
    (tmp_path / where / marker).write_text("", encoding="utf-8")
    assert LIMIT not in check.no_runner_reason(tmp_path)


def test_ac_001_hm_check_reports_it_degraded(tmp_path: Path) -> None:
    root = init_project(tmp_path / "p")
    (root / "package.json").write_text("{}\n", encoding="utf-8")
    write_spec(root, [mech_ac("AC-001", test_ids=["test/a.test.js::a"])])
    result = check.run(check.Options(slug="demo", root=root, red=True, offline=True))
    assert result["exit"] == check.EXIT_DEGRADED, result
    assert LIMIT in result["sections"]["ac"]["reason"]
