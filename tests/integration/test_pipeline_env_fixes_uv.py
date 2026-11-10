"""SPEC-pipeline-env-fixes AC-002: the rendered prefix under real uv keeps a project clean."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sysconfig
import venv
from pathlib import Path

import pytest

from harness_maker import check, spec_machine, synthesize
from harness_maker.interview import _build_answers
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import render

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not on PATH")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args],
        cwd=cwd, check=True, capture_output=True, text=True, timeout=60,
    ).stdout  # fmt: skip


def _porcelain_paths(cwd: Path) -> list[str]:
    return [ln[3:] for ln in _git(cwd, "status", "--porcelain").splitlines() if ln]


def _run(argv: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=cwd, input=stdin, capture_output=True, text=True, timeout=600, check=False
    )


def test_ac_002_project_without_a_tracked_lock_stays_clean_and_lands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "proj"
    base.mkdir()
    _git(base, "init", "-q", "-b", "main")
    # `hm worktree task-land` commits by itself, so the identity lives in the repository.
    _git(base, "config", "user.name", "T")
    _git(base, "config", "user.email", "t@e.com")
    (base / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1.0"\n')
    (base / ".gitignore").write_text(".venv/\n.worktrees/\n")
    # As a real render does it: a checkout under the home directory is written as `$HOME/…`
    # (CI runs under /home/runner), and the calls below expand it the way a shell would.
    ref = synthesize._portablize_ref(str(REPO_ROOT))
    monkeypatch.setattr(synthesize, "_compute_install_ref", lambda: ref)
    answers = _build_answers(locale="en", targets=[Target.CLAUDE_CODE], preset=Preset.SIDE)
    render(synthesize.synthesize(ProjectProfile(), answers, preset=Preset.SIDE), base / ".claude")
    _git(base, "add", "-A")
    _git(base, "commit", "-q", "-m", "init")

    # The prefix as the stage tells the model to type it, not one this test builds.
    spec = (base / ".claude" / "commands" / "hm" / "spec.md").read_text(encoding="utf-8")
    stated = re.search(r"as `(uv run [^`]+?) hm …`", spec)
    assert stated is not None
    prefix = shlex.split(os.path.expandvars(stated.group(1)))

    preflight = _run([*prefix, "hm", "worktree", "task-preflight", "demo", str(base)], base)
    assert preflight.returncode == 0, preflight.stderr[-600:]
    wt = Path(preflight.stdout.strip().splitlines()[-1])

    settings = json.loads((base / ".claude" / "settings.json").read_text(encoding="utf-8"))
    hook = next(
        h["command"]
        for group in settings["hooks"]["PreToolUse"]
        for h in group["hooks"]
        if "worktree_gate" in h["command"]
    )
    payload = {"tool_name": "Write", "cwd": str(wt), "tool_input": {"file_path": str(wt / "x.py")}}
    gate = _run(shlex.split(os.path.expandvars(hook)), wt, json.dumps(payload))
    assert gate.returncode == 0, gate.stderr[-600:]

    checked = _run([*prefix, "hm", "check", "--slug", "demo"], wt)
    report = json.loads(checked.stdout.strip().splitlines()[-1])
    assert "tracked uv.lock" in report["sections"]["gates"].get("reason", "")

    assert all(path.startswith(".claude/") for path in _porcelain_paths(base))
    assert _porcelain_paths(wt) == []
    for tree in (base, wt):
        assert not (tree / ".venv").exists()
        assert not (tree / "uv.lock").exists()

    # A worktree with its own interpreter: the runner hm picks judges the test.
    venv.create(wt / ".venv", with_pip=False)
    site = next((wt / ".venv" / "lib").glob("python*/site-packages"))
    (site / "_host.pth").write_text(sysconfig.get_paths()["purelib"] + "\n", encoding="utf-8")
    (wt / "tests").mkdir()
    (wt / "tests" / "test_demo.py").write_text(
        "def test_ac_001_demo():\n    assert False, 'not built yet'\n", encoding="utf-8"
    )
    runner = spec_machine.collect_runner(wt)
    assert runner[0] == str(wt / ".venv" / "bin" / "python")
    tid = "tests/test_demo.py::test_ac_001_demo"
    assert check.run_tests(wt, runner, [tid])[tid].outcome == "failed"

    (wt / "demo.py").write_text("X = 1\n", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "feat: demo")
    land = _run([*prefix, "hm", "worktree", "task-land", "demo", str(base)], base)
    assert land.returncode == 0, land.stderr[-600:]
    assert _git(base, "log", "-1", "--format=%s").strip() == "feat: demo"
