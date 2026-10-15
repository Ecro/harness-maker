"""SPEC-hm-light-lane-s3d: `verification_cache run --spec-slug` derives the gates from a trusted
light SPEC, in the project's `.venv`, only when the repo has no CI file.

AC-001's oracle is the 4bd3d3d8 module, run on the same fixture cells by
`tests/fixtures/light_lane_s3d/capture.py.txt` before any edit. AC-002…004's rows are the SPEC's
golden tables; `<py>` is the literal `<root>/.venv/bin/python` of each tmp fixture, and the gates
run a stub interpreter that logs what it was asked to run.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_maker.observability import verification_cache as vc
from tests.unit import light_lane_s3d_fixture as fx

GOLDEN: dict[str, Any] = json.loads((fx.GOLDENS / "run_4bd3d3d8.json").read_text(encoding="utf-8"))
SLUG = fx.SLUG
#: A slug that cannot occur in a tmp path, so "not echoed" cannot pass or fail by accident.
UNIQUE_SLUG = "qz7-slug-s3d"
IRR = [{"id": "IRR-001", "decision": "d", "category": "c", "rationale": "r", "source": "spec"}]

#: Unit-separated, so a path with a space stays one field.
_SEP = "\x1f"
#: The stub logs its full argv first, before any other import, so a slow start under load
#: cannot hide that the gate was started (the timeout row).
_STUB = """#!{exe}
import os, sys
args = sys.argv[1:]
tool = args[1] if args[:1] == ["-m"] and len(args) > 1 else ""
log = os.environ.get("S3D_LOG")
if log:
    with open(log, "a", encoding="utf-8") as f:
        f.write("\\x1f".join(sys.argv) + "\\n")
import pathlib, time
if os.environ.get("S3D_SLEEP_" + tool):
    time.sleep(float(os.environ["S3D_SLEEP_" + tool]))
if os.environ.get("S3D_MUTATE_" + tool):
    pathlib.Path(os.environ["S3D_MUTATE_" + tool]).write_text("VALUE = 2\\n")
if tool in os.environ.get("S3D_MISSING", "").split(","):
    print(sys.argv[0] + ": No module named " + tool, file=sys.stderr)
    sys.exit(1)
sys.exit(int(os.environ.get("S3D_RC_" + tool, "0")))
"""


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HARNESS_MAKER_CACHE_DIR", str(home / "cache"))
    monkeypatch.setenv("S3D_LOG", str(tmp_path / "gates.log"))
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    for tool in ("ruff", "mypy", "pytest"):
        for knob in ("RC", "SLEEP", "MUTATE"):
            monkeypatch.delenv(f"S3D_{knob}_{tool}", raising=False)
    monkeypatch.delenv("S3D_MISSING", raising=False)
    # Speed only: the key's tool-version probe spawns four interpreters per call.
    monkeypatch.setattr(vc, "_tool_versions", lambda root: {})


def _markers(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "home" / "cache" / "verify").glob("*.json"))


def _gates(tmp_path: Path) -> list[list[str]]:
    """The full argv of every gate the stub interpreter ran, in order."""
    log = tmp_path / "gates.log"
    if not log.is_file():
        return []
    return [line.split(_SEP) for line in log.read_text(encoding="utf-8").splitlines()]


def _tools(tmp_path: Path) -> list[str]:
    return [argv[2] for argv in _gates(tmp_path)]


def _stub_python(root: Path) -> Path:
    py = root / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text(_STUB.format(exe=sys.executable), encoding="utf-8")
    py.chmod(0o755)
    (root / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    return py


def _py(root: Path) -> str:
    return shlex.quote(str(root.resolve() / ".venv" / "bin" / "python"))


def _light_repo(
    root: Path,
    *,
    pyproject: str | None = None,
    venv: bool = True,
    ci: str = "absent_dir",
    slug: str = SLUG,
) -> None:
    """No CI file, a trusted exempt light pytest SPEC, and (by default) a stub `.venv`."""
    fx.init_repo(root, ci)
    if pyproject is not None:
        (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    if venv:
        _stub_python(root)
    fx.write_spec(root, slug=slug)


def _run(root: Path, *extra: str, slug: str = SLUG) -> tuple[int, dict[str, Any], str]:
    code, out, err = fx.run_cli(
        vc, ["run", "--root", str(root), "--mode", "relevant", "--spec-slug", slug, *extra]
    )
    lines = out.strip().splitlines()
    assert len(lines) == 1, out
    return code, json.loads(lines[0]), err


# ── AC-001 ──────────────────────────────────────────────────────────────────


def test_golden_covers_the_domain() -> None:
    assert GOLDEN["source_sha"] == "4bd3d3d8"
    expected = {fx.golden_key(ci, spec, suite) for ci, _f, spec, suite in fx.ac001_cells()}
    assert set(GOLDEN["cells"]) == expected
    assert len(fx.ac001_cells()) == 6 * 2 * 3 * 2 - 2 * 3 * 2


@pytest.mark.parametrize(
    ("ci", "flag", "spec", "suite"), fx.ac001_cells(), ids=["/".join(c) for c in fx.ac001_cells()]
)
def test_outside_the_opt_in_case_matches_4bd3d3d8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ci: str,
    flag: str,
    spec: str,
    suite: str,
) -> None:
    root = tmp_path / "repo"
    fx.build_cell(root, ci, spec)
    extra = ["--spec-slug", SLUG] if flag == "on" else []
    keys: list[str] = []
    got = fx.observe_cell(
        vc, root, tmp_path / "home" / "cache", fx.SUITES[suite], extra, monkeypatch.setattr, keys
    )
    assert got == GOLDEN["cells"][fx.golden_key(ci, spec, suite)]
    # The masked key is this cell's own relevant key, not merely some key in the same place.
    assert all(key == vc.compute_relevant_skip_key(root) for key in keys)


# ── AC-002 ──────────────────────────────────────────────────────────────────

_PROJECT = '[project]\nname = "t"\nversion = "0.1.0"\n'
PLAN_TABLE: dict[str, tuple[str | None, list[str]]] = {
    "no [tool.ruff], no [tool.mypy]": (
        _PROJECT + '\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        ["<py> -m pytest"],
    ),
    "[tool.ruff], no [tool.mypy]": (
        _PROJECT + "\n[tool.ruff]\nline-length = 100\n",
        ["<py> -m ruff check .", "<py> -m pytest"],
    ),
    "[tool.mypy] without files, no [tool.ruff]": (
        _PROJECT + "\n[tool.mypy]\nstrict = true\n",
        ["<py> -m mypy .", "<py> -m pytest"],
    ),
    "[tool.mypy] with files, no [tool.ruff]": (
        _PROJECT + '\n[tool.mypy]\nfiles = ["src"]\n',
        ["<py> -m mypy", "<py> -m pytest"],
    ),
    "[tool.ruff.lint] only, [tool.mypy] with files": (
        _PROJECT + '\n[tool.ruff.lint]\nselect = ["E"]\n\n[tool.mypy]\nfiles = ["src"]\n',
        ["<py> -m ruff check .", "<py> -m mypy", "<py> -m pytest"],
    ),
    "[tool.ruffx] or [tool.mypy_extra] only": (
        _PROJECT + "\n[tool.ruffx]\na = 1\n\n[tool.mypy_extra]\nb = 1\n",
        ["<py> -m pytest"],
    ),
    "pyproject.toml absent": (None, ["<py> -m pytest"]),
    "[tool.mypy] with packages": (
        _PROJECT + '\n[tool.mypy]\npackages = ["app"]\n',
        ["<py> -m mypy", "<py> -m pytest"],
    ),
    "[tool.mypy] with modules": (
        _PROJECT + '\n[tool.mypy]\nmodules = ["app"]\n',
        ["<py> -m mypy", "<py> -m pytest"],
    ),
    "[tool.ruff] and [tool.mypy] without files": (
        _PROJECT + "\n[tool.ruff]\nline-length = 100\n\n[tool.mypy]\nstrict = true\n",
        ["<py> -m ruff check .", "<py> -m mypy .", "<py> -m pytest"],
    ),
}


@pytest.mark.parametrize("case", [*PLAN_TABLE, "root path containing a space"])
def test_plan_follows_project_configuration(tmp_path: Path, case: str) -> None:
    if case == "root path containing a space":
        root = tmp_path / "with space" / "repo"
        pyproject, expected = None, ["<py> -m pytest"]
    else:
        root = tmp_path / "repo"
        pyproject, expected = PLAN_TABLE[case]
    _light_repo(root, pyproject=pyproject)
    code, out, err = _run(root)
    py = _py(root)
    assert code == 0, err
    golden = [c.replace("<py>", py) for c in expected]
    assert out["commands"] == golden
    assert out["gate_source"] == "spec"
    for cmd in out["commands"]:
        assert cmd.startswith(py + " ")
        assert shlex.split(cmd)[0] == str(root.resolve() / ".venv" / "bin" / "python")
    assert _gates(tmp_path) == [shlex.split(c) for c in golden]


# ── AC-003 ──────────────────────────────────────────────────────────────────

_NOT_LIGHT = "not on a trusted light lane"
_FRAMEWORK = "test_framework"


def _framework(value: object) -> Any:
    def build(root: Path) -> None:
        _light_repo(root)
        fx.write_spec(root, test_framework=value)

    return build


def _spec(**kw: Any) -> Any:
    def build(root: Path) -> None:
        _light_repo(root)
        fx.write_spec(root, **kw)

    return build


def _no_venv(root: Path) -> None:
    _light_repo(root, venv=False)


def _broken_pyproject(root: Path) -> None:
    _light_repo(root, pyproject="[tool.ruff\nline-length = 1\n")


def _no_pyvenv_cfg(root: Path) -> None:
    _light_repo(root)
    (root / ".venv" / "pyvenv.cfg").unlink()


def _cfg_without_python(root: Path) -> None:
    _light_repo(root)
    (root / ".venv" / "bin" / "python").unlink()


def _dangling_python(root: Path) -> None:
    _cfg_without_python(root)
    (root / ".venv" / "bin" / "python").symlink_to(root / "nowhere" / "python3")


def _without_yml(root: Path) -> None:
    _light_repo(root, ci="dir_without_yml")


def _one_yaml(root: Path) -> None:
    """A workflows dir whose only file is `.yaml`: CI is present, so the flag is inert."""
    _light_repo(root)
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yaml").write_text(
        "name: ci\non: [push]\njobs:\n  b:\n    runs-on: x\n    steps:\n      - run: echo hi\n"
    )
    fx._git(root, "add", "-A")
    fx._git(root, "commit", "-q", "-m", "ci")


def _ci_deleted_in_tree(root: Path) -> None:
    _light_repo(root, ci="readable")
    (root / ".github" / "workflows" / "ci.yml").unlink()


def _head_tool_dropped(tool: str) -> Any:
    def build(root: Path) -> None:
        _light_repo(root, pyproject=_PROJECT + f"\n[tool.{tool}]\nstrict = true\n")
        fx._git(root, "add", "pyproject.toml")
        fx._git(root, "commit", "-q", "-m", "config")
        (root / "pyproject.toml").write_text(_PROJECT, encoding="utf-8")

    return build


def _head_pyproject_not_utf8(root: Path) -> None:
    _light_repo(root, pyproject=_PROJECT)
    (root / "pyproject.toml").write_bytes(_PROJECT.encode() + b"# caf\xe9\n")
    fx._git(root, "add", "pyproject.toml")
    fx._git(root, "commit", "-q", "-m", "latin-1 comment")
    (root / "pyproject.toml").write_text(_PROJECT, encoding="utf-8")


def _unborn_head(root: Path) -> None:
    _light_repo(root)
    fx._git(root, "update-ref", "-d", "HEAD")


def _other_config(name: str) -> Any:
    def build(root: Path) -> None:
        _light_repo(root)
        (root / name).write_text("[mypy]\n" if "mypy" in name else "line-length = 100\n")

    return build


#: (builder, slug, expected exit, the stderr fragment naming why — None on a pass).
TRUST_TABLE: dict[str, tuple[Any, str, int, str | None]] = {
    "exempt light pytest, .venv, passing suite": (_light_repo, SLUG, 0, None),
    "same, approved by a human stamp": (_spec(approval="human"), SLUG, 0, None),
    "lane full, approved": (_spec(lane="full", approval="human"), SLUG, 3, _NOT_LIGHT),
    "lane light, no approval": (_spec(approval="none"), SLUG, 3, _NOT_LIGHT),
    "lane light, edited after approval": (_spec(approval="invalid"), SLUG, 3, _NOT_LIGHT),
    "lane light, approved, irreversible [IRR-001]": (
        _spec(approval="human", irreversible=IRR),
        SLUG,
        3,
        _NOT_LIGHT,
    ),
    "test_framework Pytest": (_framework("Pytest"), SLUG, 3, _FRAMEWORK),
    "test_framework 'pytest '": (_framework("pytest "), SLUG, 3, _FRAMEWORK),
    "test_framework pytest + hypothesis": (_framework("pytest + hypothesis"), SLUG, 3, _FRAMEWORK),
    "test_framework unittest": (_framework("unittest"), SLUG, 3, _FRAMEWORK),
    "test_framework ''": (_framework(""), SLUG, 3, _FRAMEWORK),
    "test_framework missing": (_framework(fx._ABSENT), SLUG, 3, _FRAMEWORK),
    "test_framework a list": (_framework(["pytest"]), SLUG, 3, _FRAMEWORK),
    "test_framework a number": (_framework(1), SLUG, 3, _FRAMEWORK),
    "test_framework null": (_framework(None), SLUG, 3, _FRAMEWORK),
    "test_framework true": (_framework(True), SLUG, 3, _FRAMEWORK),
    "no .venv/bin/python": (_no_venv, SLUG, 3, ".venv/bin/python"),
    ".venv without pyvenv.cfg": (_no_pyvenv_cfg, SLUG, 3, "pyvenv.cfg"),
    "pyvenv.cfg but no .venv/bin/python": (_cfg_without_python, SLUG, 3, ".venv/bin/python"),
    ".venv/bin/python a dangling symlink": (_dangling_python, SLUG, 3, ".venv/bin/python"),
    "workflows dir without a yml file": (_without_yml, SLUG, 0, None),
    "workflows dir with one .yaml file": (_one_yaml, SLUG, 3, "no verification command"),
    "HEAD tracks a workflow the tree lacks": (_ci_deleted_in_tree, SLUG, 3, "HEAD tracks"),
    "HEAD's [tool.ruff] dropped in the tree": (_head_tool_dropped("ruff"), SLUG, 3, "HEAD"),
    "HEAD's [tool.mypy] dropped in the tree": (_head_tool_dropped("mypy"), SLUG, 3, "HEAD"),
    "ruff.toml present": (_other_config("ruff.toml"), SLUG, 3, "ruff.toml"),
    ".ruff.toml present": (_other_config(".ruff.toml"), SLUG, 3, ".ruff.toml"),
    "mypy.ini present": (_other_config("mypy.ini"), SLUG, 3, "mypy.ini"),
    ".mypy.ini present": (_other_config(".mypy.ini"), SLUG, 3, ".mypy.ini"),
    "pyproject.toml does not parse": (_broken_pyproject, SLUG, 3, "pyproject.toml"),
    "HEAD's pyproject.toml is not UTF-8": (_head_pyproject_not_utf8, SLUG, 3, "HEAD"),
    "unborn HEAD": (_unborn_head, SLUG, 3, "cannot read HEAD"),
    "slug ..": (_light_repo, "..", 3, _NOT_LIGHT),
    "slug containing /": (_light_repo, "specs/demo", 3, _NOT_LIGHT),
    "no SPEC for the slug": (_light_repo, "other", 3, _NOT_LIGHT),
}


@pytest.mark.parametrize("case", list(TRUST_TABLE))
def test_trust_and_exit_table(tmp_path: Path, case: str) -> None:
    build, slug, expected, why = TRUST_TABLE[case]
    root = tmp_path / "repo"
    build(root)
    code, out, err = _run(root, slug=slug)
    assert code == expected == out["exit"], err
    if expected == 0:
        py = _py(root)
        assert out["gate_source"] == "spec"
        assert out["commands"] == [f"{py} -m pytest"]
        assert out["cached"] is False
        (marker,) = _markers(tmp_path)
        assert marker.stem == vc.compute_relevant_skip_key(root) == out["key"]
        data = json.loads(marker.read_text(encoding="utf-8"))
        assert data["writer"] == vc.RUN_WRITER
        assert data["checks"] == out["commands"]
        assert vc.is_run_fresh(out["key"], out["commands"]) is not None
        again_code, again, _ = _run(root, slug=slug)
        assert (again_code, again["cached"], again["gate_source"]) == (0, True, "spec")
        assert SLUG not in json.dumps(out)  # IRR-002: the slug is not echoed
        return
    assert out["commands"] == []
    assert out["cached"] is False
    assert "gate_source" not in out
    assert _markers(tmp_path) == []
    assert _gates(tmp_path) == []
    assert why is not None
    assert why in err, err


def test_trust_is_checked_before_freshness(tmp_path: Path) -> None:
    """AC-003's last row: a SPEC made untrusted outside the relevant key is not `cached: true`."""
    root = tmp_path / "repo"
    fx.init_repo(root)
    (root / ".claude").mkdir()
    (root / ".claude" / "harness.yaml").write_text("spec:\n  dir: work-docs/\n", encoding="utf-8")
    _stub_python(root)
    yml = fx.write_spec(root, spec_dir="work-docs")
    code, first, err = _run(root)
    assert code == 0, err
    assert first["commands"] == [f"{_py(root)} -m pytest"]
    key = vc.compute_relevant_skip_key(root)
    fx.invalidate_spec(yml)
    assert vc.compute_relevant_skip_key(root) == key  # the edit is outside the relevant key
    code, second, err = _run(root)
    assert (code, second["cached"], second["commands"]) == (3, False, [])
    assert _NOT_LIGHT in err
    assert len(_gates(tmp_path)) == 1


# ── AC-004 ──────────────────────────────────────────────────────────────────

_RUFF = _PROJECT + "\n[tool.ruff]\nline-length = 100\n"
#: (pyproject, env, extra argv, stub mode, expected exit, the gates that ran).
FAIL_TABLE: dict[str, tuple[str | None, dict[str, str], list[str], str, int, list[str]]] = {
    "pytest exits 1": (None, {"S3D_RC_pytest": "1"}, [], "stub", 1, ["pytest"]),
    "pytest exits 5 (no tests collected)": (
        None,
        {"S3D_RC_pytest": "5"},
        [],
        "stub",
        1,
        ["pytest"],
    ),
    "ruff configured and its command exits non-zero": (
        _RUFF,
        {"S3D_RC_ruff": "1"},
        [],
        "stub",
        1,
        ["ruff"],
    ),
    "a gate exceeds --timeout-s": (
        None,
        {"S3D_SLEEP_pytest": "20"},
        ["--timeout-s", "3"],
        "stub",
        1,
        ["pytest"],
    ),
    ".venv/bin/python cannot start": (None, {}, [], "not_executable", 1, []),
    "the tool is not installed in it": (
        None,
        {"S3D_MISSING": "pytest"},
        [],
        "stub",
        1,
        ["pytest"],
    ),
    "a relevant file changes while the gates run": (
        None,
        {"S3D_MUTATE_pytest": "<root>/src/app.py"},
        [],
        "stub",
        4,
        ["pytest"],
    ),
}


@pytest.mark.parametrize("case", list(FAIL_TABLE))
def test_spec_plan_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    pyproject, env, extra, mode, expected, ran = FAIL_TABLE[case]
    root = tmp_path / "repo"
    _light_repo(root, pyproject=pyproject, slug=UNIQUE_SLUG)
    if mode == "not_executable":
        os.chmod(root / ".venv" / "bin" / "python", 0o644)
    for name, value in env.items():
        monkeypatch.setenv(name, value.replace("<root>", str(root)))
    code, out, err = _run(root, *extra, slug=UNIQUE_SLUG)
    assert code == expected == out["exit"], err
    assert out["gate_source"] == "spec"
    assert UNIQUE_SLUG not in json.dumps(out)  # IRR-002: the slug is not echoed
    assert _markers(tmp_path) == []
    assert _tools(tmp_path) == ran
