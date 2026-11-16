"""SPEC-maker-digest-session-id S4 — Maker loads in Claude Code's default permission mode.

Maker injects its briefing with a `!` command that Claude Code checks before running it. A shell
variable in that command (`$HM_SESSION_ID`, a `$HOME` plugin path) made the check fail and the skill
never loaded: 0 model turns, no error exit. Render tests can only assert the text; whether the
host accepts it is observable only against the real CLI, and the bench cannot see it because it
runs with --dangerously-skip-permissions.

Advisory and live: it runs only with INTEGRATION=1 and a signed-in `claude` on PATH, in a throwaway
project, and costs about a cent. A checkout under the home directory renders the `~/…` plugin
path, the form every plugin-cache install has; only there does the load depend on the skill's own
`world_model` grant. Elsewhere the path is absolute and the project `settings.json` rule matches the
command too, so the run still proves the variable is gone but not that the grant matches.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "bench_light_lane.py"
_GIT = ["git", "-c", "user.name=hm-live", "-c", "user.email=live@localhost"]
_GIT += ["-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"]

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION") or shutil.which("claude") is None,
    reason="live claude CLI call; set INTEGRATION=1 with claude on PATH",
)


def _bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_light_lane", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_light_lane"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


def _project(root: Path) -> Path:
    project = root / "project"
    project.mkdir()
    subprocess.run([*_GIT, "init", "-q", str(project)], check=True, timeout=60)
    subprocess.run(
        [sys.executable, "-m", "harness_maker", "make", str(project), "--autoloop",
         "--preset", "Side", "--targets", "claude-code", "--locale", "en"],
        cwd=project, check=True, capture_output=True, timeout=300,
    )  # fmt: skip
    subprocess.run([*_GIT, "add", "-A"], cwd=project, check=True, timeout=60)
    subprocess.run([*_GIT, "commit", "-qm", "seed"], cwd=project, check=True, timeout=60)
    return project


def test_maker_loads_and_gets_the_session_id_without_permission_flags(tmp_path: Path) -> None:
    bench = _bench()
    project = _project(tmp_path)
    session = str(uuid.uuid4())
    # No --dangerously-skip-permissions and no --permission-mode: the default mode is the point.
    argv = [
        "claude", "-p", "/maker", "--output-format", "json", "--max-turns", "3",
        "--model", os.getenv("HM_BENCH_MODEL", bench.DEFAULT_MODEL), "--max-budget-usd", "0.5",
        "--setting-sources", bench.SETTING_SOURCES, "--strict-mcp-config", "--session-id", session,
    ]  # fmt: skip
    proc = subprocess.run(
        argv, cwd=project, env=bench.agent_env(), stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=600, check=False,
    )  # fmt: skip
    result = bench.parse_cli_result(proc.stdout)
    assert result is not None, (proc.stdout[-2000:], proc.stderr[-2000:])
    skill = (project / ".claude/skills/maker/SKILL.md").read_text(encoding="utf-8")
    injected = next(line for line in skill.splitlines() if line.startswith("!`"))
    print(f"injected: {injected}\nresult: {str(result.get('result'))[:400]}")
    assert "permission check failed" not in str(result.get("result")), result.get("result")
    assert int(result.get("num_turns") or 0) >= 1, "the skill never reached the model"
    ledger = project / ".claude/observability/world-model.jsonl"
    assert ledger.is_file(), "the injected digest never ran"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    loads = [r for r in rows if r.get("event") == "maker_load"]
    assert loads, rows
    assert loads[0]["session_id"] == session, "the digest did not get the host's session id"
