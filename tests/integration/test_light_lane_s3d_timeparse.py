"""SPEC-hm-light-lane-s3d AC-007: the timeparse bench fixture passes Check 2 from its SPEC.

Real `uv`, real pytest, on a committed copy of `scripts/bench/timeparse`, with hm invoked as
the bench invokes it (`uv run --with <src> hm`) and harness-maker's own `.venv/bin` removed
from `PATH`, so a pass comes from the fixture's own `.venv` (which uv syncs from the fixture's
`[dependency-groups] dev`), not from the dev venv. Needs a warm uv cache or the network.
INTEGRATION=1 only: it is the main session's to run.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit import light_lane_s3d_fixture as fx

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"), reason="INTEGRATION=1 only: real uv sync and a real suite"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "scripts" / "bench" / "timeparse"
DEV_VENV_BIN = REPO_ROOT / ".venv" / "bin"
_IGNORE = shutil.ignore_patterns("__pycache__", ".venv", ".pytest_cache", "uv.lock")


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    off = {DEV_VENV_BIN.resolve()}
    if env.get("VIRTUAL_ENV"):
        off.add((Path(env["VIRTUAL_ENV"]) / "bin").resolve())
    env["PATH"] = os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep) if p and Path(p).resolve() not in off
    )
    for name in ("VIRTUAL_ENV", "HM_SESSION_ID", "UV_PROJECT_ENVIRONMENT"):
        env.pop(name, None)
    env["HARNESS_MAKER_CACHE_DIR"] = str(tmp_path / "cache")
    return env


def _call(argv: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=600, check=False
    )


def test_timeparse_passes_from_its_spec_without_the_dev_venv(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "uv is not on PATH"
    work = tmp_path / "timeparse"
    shutil.copytree(FIXTURE, work, ignore=_IGNORE)
    fx._git(work, "init", "-q")
    fx._git(work, "config", "user.name", "Fixture User")
    fx._git(work, "config", "user.email", "fixture@example.invalid")
    fx._git(work, "add", "-A")
    fx._git(work, "commit", "-q", "-m", "fixture")
    fx.write_spec(work)
    env = _env(tmp_path)
    hm = [uv, "run", "--with", str(REPO_ROOT), "hm", "observability.verification_cache"]

    # As in the probe: the first `uv run` syncs the fixture's `.venv` (with pytest, from the
    # dev group) and writes `uv.lock` before hm starts, so the key is stable after it.
    synced = _call([*hm, "key", "--root", "."], work, env)
    assert synced.returncode == 0, synced.stderr
    py = work / ".venv" / "bin" / "python"
    # Execute's GREEN step runs the suite after the last edit, so the `.pyc` files are current.
    green = _call([str(py), "-m", "pytest", "-q"], work, env)
    assert green.returncode == 0, green.stdout + green.stderr

    run = _call(
        [*hm, "run", "--root", ".", "--mode", "relevant", "--spec-slug", fx.SLUG], work, env
    )
    lines = run.stdout.strip().splitlines()
    assert lines, run.stderr
    result = json.loads(lines[-1])
    path_used = [shlex.split(cmd)[0] for cmd in result["commands"]]
    assert result["exit"] == 0, run.stderr
    assert result["gate_source"] == "spec"
    assert path_used == [str(work.resolve() / ".venv" / "bin" / "python")]
    assert str(DEV_VENV_BIN) not in " ".join(path_used)
