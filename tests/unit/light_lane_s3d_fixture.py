"""Fixture builder for SPEC-hm-light-lane-s3d, shared by the 4bd3d3d8 capture and the new tests.

One builder for both sides is AC-001's precondition: the differential compares the 4bd3d3d8
`verification_cache run` with the new one on repos built by the same code, so only the module
under test differs. It therefore uses only APIs that exist at 4bd3d3d8 (`spec_machine.approve`,
`verification_cache.main` / `_run_gate` / `_tool_versions`), and it is run against that tree by
`tests/fixtures/light_lane_s3d/capture.py.txt`.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
from collections.abc import Callable
from itertools import product
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

SLUG = "demo"
GOLDENS = Path(__file__).resolve().parents[1] / "fixtures" / "light_lane_s3d"

#: AC-001's CI states. The first two are "CI absent" (SPEC Outcomes); the rest are present.
CI_STATES: dict[str, dict[str, str] | None] = {
    "absent_dir": None,
    "dir_without_yml": {"README.md": "no workflows here\n"},
    "readable": {
        "ci.yml": (
            "name: ci\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: ruff check .\n      - run: mypy --strict src\n"
            "      - run: pytest -q\n"
        )
    },
    "unreadable": {"ci.yml": "name: ci\non: [push\njobs: {\n"},
    "no_recognised_command": {
        "ci.yml": (
            "name: ci\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: echo hello\n"
        )
    },
    "all_advisory": {
        "ci.yml": (
            "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    continue-on-error: true\n    steps:\n      - run: pytest -q\n"
        )
    },
}
CI_ABSENT = frozenset({"absent_dir", "dir_without_yml"})
SPEC_KINDS = ("none", "trusted", "untrusted")
SUITES = {"passing": 0, "failing": 1}
FLAGS = ("off", "on")


def ac001_cells() -> list[tuple[str, str, str, str]]:
    """(ci, flag, spec, suite) over AC-001's domain, minus every CI-absent + flag-on cell."""
    return [
        cell
        for cell in product(CI_STATES, FLAGS, SPEC_KINDS, SUITES)
        if not (cell[0] in CI_ABSENT and cell[1] == "on")
    ]


def golden_key(ci: str, spec: str, suite: str) -> str:
    """The 4bd3d3d8 module has no flag, so its golden for a cell does not depend on it."""
    return f"{ci}/{spec}/{suite}"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, timeout=30)


def isolate_env(home: Path) -> None:
    """Point HOME, git config and the verification cache at `home`."""
    os.environ.update(
        {
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": str(home / "no-global"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "HARNESS_MAKER_CACHE_DIR": str(home / "cache"),
        }
    )
    os.environ.pop("HM_SESSION_ID", None)


def init_repo(root: Path, ci: str = "absent_dir") -> None:
    """A committed repo with a source file, a test file and the given CI state."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Fixture User")
    _git(root, "config", "user.email", "fixture@example.invalid")
    (root / ".gitignore").write_text(".claude/*\n.venv/\n__pycache__/\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text("def test_ok():\n    assert True\n")
    files = CI_STATES[ci]
    if files is not None:
        wf = root / ".github" / "workflows"
        wf.mkdir(parents=True)
        for name, text in files.items():
            (wf / name).write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


_ABSENT = object()


def write_spec(
    root: Path,
    *,
    lane: str = "light",
    approval: str = "exempt",
    irreversible: list[dict[str, str]] | None = None,
    test_framework: object = "pytest",
    spec_dir: str = "specs",
    slug: str = SLUG,
) -> Path:
    """Write `SPEC-<slug>.md` + machine yaml; `approval` is exempt, human, none or invalid.

    `test_framework=_ABSENT` leaves the key out of the `.md` frontmatter. Returns the yaml path.
    """
    from harness_maker import spec_machine

    specs = root / spec_dir
    specs.mkdir(parents=True, exist_ok=True)
    fm: dict[str, object] = {"type": "spec", "task_slug": slug, "lane": lane}
    if test_framework is not _ABSENT:
        fm["test_framework"] = test_framework
    md = specs / f"SPEC-{slug}.md"
    md.write_text(f"---\n{yaml.safe_dump(fm, sort_keys=False)}---\n# SPEC\n", encoding="utf-8")
    doc: dict[str, Any] = {
        "schema_version": 3,
        "spec_slug": slug,
        "verification_tier": 1,
        "irreversible_decisions": irreversible or [],
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
    yml = specs / f"SPEC-{slug}.machine.yaml"
    yml.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    if approval == "none":
        return yml
    spec_machine.approve(yml, exempt=approval == "exempt")
    if approval == "invalid":
        invalidate_spec(yml)
    return yml


def invalidate_spec(yml: Path) -> None:
    """Edit an approved machine yaml so its stamp no longer matches (state `invalid`)."""
    raw = yaml.safe_load(yml.read_text(encoding="utf-8"))
    raw["ac"][0]["title"] = "edited after approval"
    yml.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def write_venv_python(root: Path) -> Path:
    """A stand-in `<root>/.venv/bin/python` (AC-001 never runs it: its gate runner is fake)."""
    py = root / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    py.chmod(0o755)
    return py


def build_cell(root: Path, ci: str, spec: str) -> None:
    """AC-001's fixture: the CI state, the SPEC kind, and a `.venv/bin/python` beside it."""
    init_repo(root, ci)
    write_venv_python(root)
    if spec == "trusted":
        write_spec(root)
    elif spec == "untrusted":
        write_spec(root, approval="none")


def run_cli(module: ModuleType, argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


_PASSED_AT = re.compile(r'"passed_at": "[^"]*"')
_SECONDS = re.compile(r'"seconds": [0-9.]+')
_KEY_FIELD = re.compile(r'"key": "([0-9a-f]{64})"')


def observe_cell(
    module: ModuleType,
    root: Path,
    cache: Path,
    rc: int,
    extra: list[str],
    patch: Callable[[object, str, object], None] = setattr,
) -> dict[str, Any]:
    """Two `run` calls with a fake gate runner: stdout, exit, the gates asked for, marker bytes.

    Normalised only where the value is the fixture's own place or time: the root path, the key
    (a hash over that path and the fixture's commit), `passed_at` and each gate's `seconds`.
    `patch` is `setattr` in the capture script and `monkeypatch.setattr` in a test.
    `_tool_versions` is stubbed for speed only: the key it feeds is masked.
    """
    argv = ["run", "--root", str(root), "--mode", "relevant", *extra]
    calls: list[str] = []
    patch(module, "_run_gate", fake_gate_runner(calls, rc))
    patch(module, "_tool_versions", lambda root: {})
    real_root = str(root.resolve())
    rounds: list[dict[str, Any]] = []
    for _ in range(2):
        code, out, _err = run_cli(module, argv)
        markers = sorted((cache / "verify").glob("*.json")) if (cache / "verify").is_dir() else []
        marker_texts = [m.read_text(encoding="utf-8") for m in markers]
        keys = list(dict.fromkeys([m.stem for m in markers] + _KEY_FIELD.findall(out)))
        rounds.append(
            {
                "exit": code,
                "stdout": _mask(out, real_root, keys),
                "gates": list(calls),
                "markers": [_mask(t, real_root, keys) for t in marker_texts],
            }
        )
    return {"rounds": rounds}


def _mask(text: str, real_root: str, keys: list[str]) -> str:
    text = text.replace(real_root, "<root>")
    for i, key in enumerate(keys):
        text = text.replace(key, f"<key{i}>")
    text = _SECONDS.sub('"seconds": "<s>"', text)
    return _PASSED_AT.sub('"passed_at": "<passed_at>"', text)


def fake_gate_runner(calls: list[str], rc: int) -> Any:
    def _fake(cmd: str, root: Path, timeout_s: float) -> tuple[int, str]:
        calls.append(cmd)
        return rc, f"output of {cmd}\n"

    return _fake


def capture_ac001(module: ModuleType, work: Path) -> dict[str, Any]:
    """Every golden cell (flag-independent), observed under `module` without the flag."""
    out: dict[str, Any] = {}
    for i, (ci, spec, suite) in enumerate(product(CI_STATES, SPEC_KINDS, SUITES)):
        cell = work / f"c{i}"
        isolate_env(cell / "home")
        root = cell / "repo"
        build_cell(root, ci, spec)
        out[golden_key(ci, spec, suite)] = observe_cell(
            module, root, cell / "home" / "cache", SUITES[suite], []
        )
    return out


def dumps(doc: object) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"
