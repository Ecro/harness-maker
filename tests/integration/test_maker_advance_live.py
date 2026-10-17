"""SPEC-maker-advance AC-005: a live Maker Resume lands an exempt task once and never pushes.

Run HM_MAKER_ADVANCE_LIVE=1 IS_SANDBOX=1 uv run pytest tests/integration/test_maker_advance_live.py.
The agent runs with --dangerously-skip-permissions inside a scratch project, so run it only in a
container or a throwaway VM. Each case is capped at --max-budget-usd 5 and 30 minutes.

What it proves: the exempt case shows Maker entering wrapup on its own after a clean execute and
landing the code once without a push. The unstamped case shows that no approval means no land; it
stops at the stamp gate. Each run gets a fixed session id and a span row from that session, so
`other_session` is false and Resume has no reason to ask who else holds the task.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SLUG = "add-fn"
pytestmark = pytest.mark.skipif(
    os.environ.get("HM_MAKER_ADVANCE_LIVE") != "1" or shutil.which("claude") is None,
    reason="opt-in live Claude Code run",
)
_GIT = ["git", "-c", "user.name=hm-live", "-c", "user.email=live@localhost"]
_GIT += ["-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"]

_SPEC_MD = """---
type: spec
task_slug: add-fn
status: approved
created: 2026-10-17
tags: [demo, spec]
test_framework: pytest
interview_rounds: 0
lane: full
---

# SPEC — add-fn

## Intent
`calc.add(a, b)` returns `a + b`.

## Acceptance Criteria
### AC-001: add returns the sum
`calc.add(2, 3) == 5` and `calc.add(-1, 1) == 0`.

## Open Questions
None.
"""

_MACHINE = """schema_version: 3
spec_slug: add-fn
verification_tier: 1
ac:
- id: AC-001
  title: add returns the sum
  type: mechanical
  test_ids:
  - tests/test_calc.py::test_add
  executable_predicate: calc.add(2, 3) == 5 and calc.add(-1, 1) == 0
  pending_test: true
  oracle_source: golden
  oracle_evidence: Integer addition; the expected sums are arithmetic facts, not read from code.
irreversible_decisions: {irr}
"""
_IRR = """
- id: IRR-001
  decision: calc.add is a public API
  category: public API/CLI contract
  rationale: callers depend on its name
  source: spec"""


def _bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench", ROOT / "scripts/bench_light_lane.py")
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bench"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop("bench", None)
    return mod


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [*_GIT, *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


def _hm(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["uv", "run", "--with", str(ROOT), "hm", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        timeout=300,
    )


def _seed(root: Path, *, exempt: bool, session: str) -> tuple[Path, Path]:
    origin, project = root / "origin.git", root / "project"
    _git(root, "init", "-q", "--bare", str(origin))
    _git(root, "init", "-q", str(project))
    (project / ".gitignore").write_text(".worktrees/\n.venv/\n__pycache__/\n", "utf-8")
    (project / "calc.py").write_text('"""Arithmetic helpers."""\n', "utf-8")
    subprocess.run(
        [sys.executable, "-m", "harness_maker", "make", str(project), "--autoloop",
         "--preset", "Side", "--targets", "claude-code", "--locale", "en", "--worktree"],
        cwd=project, check=True, capture_output=True, timeout=300,
    )  # fmt: skip
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "seed")
    _git(project, "remote", "add", "origin", str(origin))
    _git(project, "push", "-q", "origin", "main")
    _hm(project, "worktree", "task-create", SLUG, str(project))
    wt = project / ".worktrees" / SLUG
    # `hm check` runs `<root>/.venv/bin/python -m pytest`; the venv stays untracked.
    for where in (project, wt):
        subprocess.run(["uv", "venv", "-q", str(where / ".venv")], check=True, timeout=120)
        subprocess.run(
            ["uv", "pip", "install", "-q", "--python", str(where / ".venv/bin/python"), "pytest"],
            check=True, timeout=300,
        )  # fmt: skip
    (wt / "specs").mkdir(exist_ok=True)
    (wt / f"specs/SPEC-{SLUG}.md").write_text(_SPEC_MD, "utf-8")
    machine = wt / f"specs/SPEC-{SLUG}.machine.yaml"
    machine.write_text(_MACHINE.format(irr="[]" if exempt else _IRR), "utf-8")
    if exempt:
        _hm(wt, "spec_machine", "approve", "--yaml", str(machine), "--exempt")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "wip(spec): add-fn")
    # The session that wrote the SPEC is the one resuming it (the ledger is gitignored).
    span = {
        "schema_version": 1, "event": "end", "stage": "hm:spec", "cwd": str(wt),
        "base_root": str(project), "git_branch": f"hm/{SLUG}", "task_slug": SLUG,
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "session_id": session,
    }  # fmt: skip
    ledger = project / ".claude/observability/stage-spans.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(span) + "\n")
    return project, origin


def _run(project: Path, log: Path, session: str) -> dict[str, Any]:
    bench = _bench()
    prompt = f"Use the maker skill to continue the task {SLUG}."
    argv = [*bench.agent_argv("claude", prompt, bench.DEFAULT_MODEL, 150, 5.0)]
    argv += ["--session-id", session]
    proc = subprocess.Popen(
        argv, cwd=project, env=bench.agent_env(("IS_SANDBOX",)), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )  # fmt: skip
    try:
        out, err = proc.communicate(timeout=1800)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
    log.write_text(out + "\n--- stderr ---\n" + err, "utf-8")
    result = bench.parse_cli_result(out)
    # A crash, an auth failure or a budget stop also lands nothing; never count it as a stop.
    assert result is not None, f"no CLI result: {log}"
    assert not result.get("is_error"), f"CLI error: {log}"
    assert result.get("subtype") == "success", f"{result.get('subtype')}: {log}"
    return dict(result)


@pytest.mark.parametrize(
    ("exempt", "expected"), [(True, 1), (False, 0)], ids=["exempt", "unstamped"]
)
def test_ac_005_resumed_task_lands_once_unapproved_never(
    exempt: bool, expected: int, tmp_path_factory: pytest.TempPathFactory
) -> None:
    root = tmp_path_factory.mktemp(f"live-{'exempt' if exempt else 'unstamped'}")
    session = str(uuid.uuid4())
    project, origin = _seed(root, exempt=exempt, session=session)
    before = int(_git(project, "rev-list", "--count", "main"))
    remote = _git(origin, "for-each-ref")
    _run(project, root / "transcript.json", session)
    landed = int(_git(project, "rev-list", "--count", "main")) - before
    assert landed == expected, f"transcript: {root / 'transcript.json'}"
    assert _git(origin, "for-each-ref") == remote, "the run pushed"
    if exempt:
        assert "def add" in _git(project, "show", "main:calc.py"), "the land carried no code"
