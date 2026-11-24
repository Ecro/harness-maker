"""SPEC-nightly-py313-venv: a scrubbed-env `uv run` must not rebuild the project venv."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._uv_env import uv_subprocess_env

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_CALLERS = (
    REPO_ROOT / "tests/e2e/test_verify_health_dashboard.py",
    REPO_ROOT / "tests/e2e/test_reconcile_orphan_sweep.py",
)
OLD_KEYS = ("PATH", "HOME", "USER", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")
KEYS = (*OLD_KEYS, "UV_PYTHON", "UV_PYTHON_INSTALL_DIR", "UV_CACHE_DIR")


def test_ac_001_helper_forwards_interpreter_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in KEYS:
        monkeypatch.setenv(key, f"value-of-{key}")
    monkeypatch.setenv("HM_UNRELATED_PROBE", "leak")
    got = uv_subprocess_env()
    assert {k: got.get(k) for k in KEYS} == {k: f"value-of-{k}" for k in KEYS}
    assert "HM_UNRELATED_PROBE" not in got
    assert all(k in KEYS or k.startswith("UV_") for k in got)

    for key in ("UV_PYTHON", "UV_PYTHON_INSTALL_DIR", "VIRTUAL_ENV"):
        monkeypatch.delenv(key)
    got = uv_subprocess_env()
    assert not {"UV_PYTHON", "UV_PYTHON_INSTALL_DIR", "VIRTUAL_ENV"} & set(got)
    assert got["UV_CACHE_DIR"] == "value-of-UV_CACHE_DIR"


def _venv_minor(project: Path) -> str:
    for line in (project / ".venv/pyvenv.cfg").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() in {"version_info", "version"}:
            return ".".join(value.strip().split(".")[:2])
    raise AssertionError("pyvenv.cfg has no version line")


def _scratch_project(where: Path, uv: str, base_env: dict[str, str]) -> Path:
    where.mkdir()
    (where / "pyproject.toml").write_text(
        '[project]\nname = "probe"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n',
        encoding="utf-8",
    )
    (where / ".python-version").write_text("3.12\n", encoding="utf-8")
    subprocess.run(
        [uv, "sync", "-q", "--offline"],
        cwd=where,
        env={**base_env, "UV_PYTHON": "3.13"},
        check=True,
        capture_output=True,
        timeout=120,
    )
    assert _venv_minor(where) == "3.13"
    return where


def test_ac_002_uv_run_keeps_venv_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")
    for key in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("UV_PYTHON", "3.13")
    # Both arms may see uv's managed interpreters (CI installs them there); only the pin differs.
    seen = (*OLD_KEYS, "UV_PYTHON_INSTALL_DIR")
    base = {k: os.environ[k] for k in seen if k in os.environ}
    for minor in ("3.12", "3.13"):
        found = subprocess.run(
            [uv, "python", "find", "--offline", "--no-project", minor],
            cwd=tmp_path,
            env=base,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if found.returncode != 0:
            # Nightly's py313 job is the one CI run with both interpreters; never skip there.
            if os.environ.get("GITHUB_ACTIONS") and os.environ.get("UV_PYTHON") == "3.13":
                pytest.fail(f"uv cannot find Python {minor} in the py313 job: {found.stderr}")
            pytest.skip(f"uv cannot find Python {minor} offline")

    fixed = _scratch_project(tmp_path / "fixed", uv, base)
    subprocess.run(
        [uv, "run", "--offline", "python", "-V"],
        cwd=fixed,
        env=uv_subprocess_env(),
        check=True,
        capture_output=True,
        timeout=120,
    )
    assert _venv_minor(fixed) == "3.13"

    control = _scratch_project(tmp_path / "control", uv, base)
    subprocess.run(
        [uv, "run", "--offline", "python", "-V"],
        cwd=control,
        env=base,
        check=True,
        capture_output=True,
        timeout=120,
    )
    assert _venv_minor(control) == "3.12", "control no longer reproduces the venv rebuild"


@pytest.mark.parametrize("caller", E2E_CALLERS, ids=lambda p: p.name)
def test_ac_003_e2e_callers_use_helper(caller: Path) -> None:
    src = caller.read_text(encoding="utf-8")
    assert "uv_subprocess_env" in src
    assert '"UV_PROJECT_ENVIRONMENT"' not in src
