"""SPEC-hm-overhaul-p1 AC-008: no hook command a 0.62 render shipped errors after the upgrade.

The corpus is every command in `.claude/settings.json`, `.codex/hooks.json` and
`.cursor/hooks.json` of db19f023 renders. Each one runs through `/bin/sh` as the host would,
with its `uv run --with <ref>` pointed at HEAD (and, for the reference exit, at db19f023), on
every payload kind with and without live loop and autopilot markers.
"""

from __future__ import annotations

import itertools
import json
import re
import shutil
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest

from harness_maker import autopilot
from harness_maker.loop_marker import format_marker_content
from harness_maker.models import AtomicStage
from tests._overhaul_p1_ref import REPO_ROOT, clean_env, init_project, ref_root, run_make

_WORKERS = 8
_WITH_RE = re.compile(r"--with\s+(?:\"[^\"]*\"|'[^']*'|\S+)")
_HOOK_FILES = (".claude/settings.json", ".codex/hooks.json", ".cursor/hooks.json")
_SESSION = "s-ac008"

_SHIM = """#!{python}
import os, sys
args = sys.argv[1:]
if not args or args[0] != "run":
    sys.exit("uv shim: unsupported call " + repr(args))
args, ref = args[1:], None
while args and args[0].startswith("--"):
    if args[0] == "--with":
        ref, args = args[1], args[2:]
    else:
        args = args[1:]
if ref is None or not args or args[0] != "python":
    sys.exit("uv shim: unsupported call " + repr(sys.argv))
env = dict(os.environ, PYTHONPATH=os.path.join(ref, "src"))
os.execve({python!r}, [{python!r}, *args[1:]], env)
"""


@dataclass(frozen=True)
class _Hook:
    file: str
    event: str
    matcher: str
    command: str


def _strip_frontmatter(text: str) -> str:
    return text.split("---", 2)[2] if text.startswith("---") else text


def _hooks_of(project: Path) -> list[_Hook]:
    out: list[_Hook] = []
    for rel in _HOOK_FILES:
        path = project / rel
        if not path.is_file():
            continue
        data = json.loads(_strip_frontmatter(path.read_text(encoding="utf-8")))
        for event, entries in data.get("hooks", {}).items():
            for entry in entries:
                matcher = str(entry.get("matcher") or "")
                commands = (
                    [entry["command"]]
                    if "command" in entry
                    else [h["command"] for h in entry.get("hooks", [])]
                )
                out.extend(_Hook(rel, event, matcher, c) for c in commands)
    return out


def _tool(matcher: str) -> tuple[str, dict[str, object]]:
    if "apply_patch" in matcher and "Write" not in matcher:
        patch = "*** Begin Patch\n*** Add File: src/app.py\n+x = 1\n*** End Patch\n"
        return "apply_patch", {"command": patch, "input": patch}
    if "Write" in matcher or "Edit" in matcher:
        return "Write", {"file_path": "src/app.py", "content": "x = 1\n"}
    return "Bash", {"command": "ls -la"}


def _payloads(hook: _Hook, project: Path) -> dict[str, str]:
    tool_name, tool_input = _tool(hook.matcher)
    if "file_path" in tool_input:
        tool_input = {**tool_input, "file_path": str(project / "src" / "app.py")}
    event = hook.event[0].upper() + hook.event[1:]
    camel = hook.event[0].lower() + hook.event[1:]
    common: dict[str, object] = {"tool_name": tool_name, "tool_input": tool_input}
    if event == "PostToolUse":
        common["tool_response"] = {"stdout": "", "success": True}
    if event == "PreCompact":
        common["trigger"] = "auto"
    if event == "SessionStart":
        common["source"] = "startup"
    if event == "Stop":
        common["stop_hook_active"] = False
    claude = {
        "session_id": _SESSION,
        "transcript_path": str(project / "transcript.jsonl"),
        "cwd": str(project),
        "hook_event_name": event,
        **common,
    }
    codex = {"session_id": _SESSION, "turn_id": "t1", "cwd": str(project), "hook_event_name": event}
    cursor = {
        "cursor_version": "2.6.0",
        "conversation_id": "c1",
        "generation_id": "g1",
        "hook_event_name": camel,
        "workspace_roots": [str(project)],
        "status": "completed",
        **common,
    }
    return {
        "empty": "",
        "garbage": "{not json",
        "claude": json.dumps(claude),
        "codex": json.dumps({**codex, **common}),
        "cursor": json.dumps(cursor),
    }


def _arm_markers(project: Path) -> None:
    worktree = project / ".worktrees" / "execute-ac008"
    worktree.mkdir(parents=True, exist_ok=True)
    (project / ".claude" / ".hm-loop-active").write_text(
        format_marker_content(_SESSION, [worktree]), encoding="utf-8"
    )
    autopilot.write(
        project,
        level="auto_safe",
        pipeline=[AtomicStage("spec"), AtomicStage("execute")],
        claude_session_id=_SESSION,
    )


def _run(
    command: str, root: Path, project: Path, home: Path, payload: str, kind: str
) -> tuple[int, str]:
    pointed = _WITH_RE.sub(lambda _: f'--with "{root}"', command, count=1)
    extra = {"PATH": f"{home / '.local' / 'bin'}:{clean_env(home=home, src=root)['PATH']}"}
    if kind == "cursor":
        extra["CURSOR_PROJECT_DIR"] = str(project)
    elif kind != "codex":
        extra["CLAUDE_PROJECT_DIR"] = str(project)
        extra["CLAUDE_ENV_FILE"] = str(project / ".claude-env")
    env = clean_env(home=home, src=root / "src", **extra)
    env.pop("PYTHONPATH")
    try:
        r = subprocess.run(
            ["/bin/sh", "-c", pointed],
            input=payload,
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return -9, "timeout"
    return r.returncode, r.stderr


@pytest.fixture(scope="module")
def corpus(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[tuple[str, str], tuple[_Hook, Path]]]:
    """Every distinct (event, command) of the db19f023 renders, with the tree it came from."""
    base = tmp_path_factory.mktemp("ac008")
    ref = ref_root(base)
    cells = list(itertools.product(("Side", "Production"), ("block", "warn"), (True, False)))

    def render(cell: tuple[str, str, bool]) -> Path:
        preset, strictness, worktree = cell
        project = init_project(base / f"render-{preset}-{strictness}-{worktree}")
        r = run_make(
            project,
            [
                "--autoloop",
                "--preset",
                preset,
                "--strictness",
                strictness,
                "--targets",
                "claude-code,cursor,codex",
                "--worktree" if worktree else "--no-worktree",
            ],
            src=ref / "src",
            home=base / "render-home",
        )
        assert r.returncode == 0, r.stderr[-2000:]
        return project

    with ThreadPoolExecutor(_WORKERS) as pool:
        projects = list(pool.map(render, cells))
    found: dict[tuple[str, str], tuple[_Hook, Path]] = {}
    for project in projects:
        for hook in _hooks_of(project):
            key = (hook.event.lower(), _WITH_RE.sub("--with <REF>", hook.command))
            found.setdefault(key, (hook, project))
    return ref, found


def _copy(project: Path, dest: Path, *, markers: bool) -> Path:
    shutil.copytree(project, dest, ignore=shutil.ignore_patterns(".backup-*"), symlinks=True)
    if markers:
        _arm_markers(dest)
    return dest


def _shim_home(home: Path) -> Path:
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "uv"
    shim.write_text(_SHIM.format(python=sys.executable), encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    return home


def test_ac008_every_shipped_hook_command_is_safe(
    tmp_path: Path, corpus: tuple[Path, dict[tuple[str, str], tuple[_Hook, Path]]]
) -> None:
    ref, hooks = corpus
    files = {h.file for h, _ in hooks.values()}
    assert files == set(_HOOK_FILES), f"corpus misses a hook file: {sorted(files)}"
    home = _shim_home(tmp_path / "home")
    jobs = [
        (i, hook, project, kind, payload, markers)
        for i, (hook, project) in enumerate(hooks.values())
        for markers in (False, True)
        for kind, payload in _payloads(hook, project).items()
    ]

    def cell(job: tuple[int, _Hook, Path, str, str, bool]) -> str | None:
        i, hook, project, kind, _, markers = job
        tag = f"{i}-{kind}-{markers}"
        head_p = _copy(project, tmp_path / f"head-{tag}", markers=markers)
        ref_p = _copy(project, tmp_path / f"ref-{tag}", markers=markers)
        head_payload = _payloads(hook, head_p)[kind]
        ref_payload = _payloads(hook, ref_p)[kind]
        head_exit, head_err = _run(hook.command, REPO_ROOT, head_p, home, head_payload, kind)
        ref_exit, _ = _run(hook.command, ref, ref_p, home, ref_payload, kind)
        ok = head_exit == 0 or (head_exit == 2 and ref_exit == 2)
        if ok and "Traceback" not in head_err:
            return None
        return (
            f"{hook.file} {hook.event} {hook.command.split('python -m')[-1].strip()} "
            f"[{kind}, markers={markers}]: HEAD exit {head_exit}, db19f023 exit {ref_exit}: "
            f"{head_err.strip()[-300:]}"
        )

    with ThreadPoolExecutor(_WORKERS) as pool:
        failures = [f for f in pool.map(cell, jobs) if f]
    assert not failures, f"{len(failures)}/{len(jobs)} cells violate AC-008:\n" + "\n".join(
        failures[:30]
    )
