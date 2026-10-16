"""Cursor runs `.claude/settings.json` hooks too; the Claude copy must stand down there."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker.hook_host import CURSOR_HOST_MARKER, is_claude_copy_in_cursor

SRC = Path(__file__).resolve().parents[2] / "src"
TEMPLATES = SRC / "harness_maker" / "templates"


def _cursor_payload(root: Path) -> dict[str, object]:
    return {
        "cursor_version": "2.6.0",
        "conversation_id": "c1",
        "session_id": "c1",
        "hook_event_name": "postToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(root / "a.py")},
        "trigger": "auto",
        "workspace_roots": [str(root)],
    }


def _marked_project(root: Path, *, marked: bool = True) -> Path:
    (root / ".cursor").mkdir()
    cmd = f"{CURSOR_HOST_MARKER} uv run x" if marked else "uv run x"
    (root / ".cursor" / "hooks.json").write_text(
        json.dumps({"version": 1, "hooks": {"stop": [{"command": cmd}]}}), encoding="utf-8"
    )
    return root


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("HM_HOOK_HOST", "CURSOR_PROJECT_DIR", "CLAUDE_PROJECT_DIR"):
        monkeypatch.delenv(var, raising=False)


def test_claude_copy_under_cursor_stands_down(tmp_path: Path) -> None:
    root = _marked_project(tmp_path)
    assert is_claude_copy_in_cursor(_cursor_payload(root))
    assert is_claude_copy_in_cursor(json.dumps(_cursor_payload(root)))


def test_claude_code_payload_never_stands_down(tmp_path: Path) -> None:
    _marked_project(tmp_path)
    payload = {"session_id": "s", "hook_event_name": "PostToolUse", "cwd": str(tmp_path)}
    assert not is_claude_copy_in_cursor(payload)


def test_cursor_copy_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _marked_project(tmp_path)
    monkeypatch.setenv("HM_HOOK_HOST", "cursor")
    assert not is_claude_copy_in_cursor(_cursor_payload(root))


def test_unmarked_cursor_render_keeps_both(tmp_path: Path) -> None:
    """An old `.cursor/hooks.json` has no marker: standing down would leave Cursor with none."""
    root = _marked_project(tmp_path, marked=False)
    assert not is_claude_copy_in_cursor(_cursor_payload(root))
    assert not is_claude_copy_in_cursor(_cursor_payload(tmp_path / "missing"))


def test_malformed_text_is_not_a_cursor_copy() -> None:
    assert not is_claude_copy_in_cursor("{nope")
    assert not is_claude_copy_in_cursor("[]")
    assert not is_claude_copy_in_cursor("")


def test_every_cursor_command_carries_the_marker() -> None:
    """The last shipped Cursor hooks template (db19f023, 0.62) marked every command.

    The template left with the Cursor target (0.63.0), but a kept `.cursor/hooks.json`
    still runs, so the stand-down below is only sound if every command it can hold is marked.
    """
    text = subprocess.run(
        ["git", "show", "db19f023:src/harness_maker/templates/cursor/hooks.json.j2"],
        cwd=SRC.parent,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    commands = re.findall(r'"command": "([^"\\]*(?:\\.[^"\\]*)*)"', text)
    assert commands
    assert all(c.startswith(CURSOR_HOST_MARKER + " ") for c in commands)


def _settings_hook_commands() -> list[list[str]]:
    found: set[tuple[str, ...]] = set()
    for tpl in (TEMPLATES / "settings").glob("*.json.j2"):
        text = tpl.read_text(encoding="utf-8")
        for m in re.finditer(r"python -m (harness_maker\.[\w.]+)((?: [-\w]+)*)", text):
            found.add((m.group(1), *m.group(2).split()))
    return [list(c) for c in sorted(found)]


SETTINGS_HOOKS = _settings_hook_commands()


def _run(cmd: list[str], root: Path, payload: dict[str, object], **env: str) -> str:
    full_env = {**os.environ, "PYTHONPATH": str(SRC), "CURSOR_PROJECT_DIR": str(root), **env}
    for var in ("HM_HOOK_HOST", "CLAUDE_PROJECT_DIR", "CLAUDE_ENV_FILE"):
        if var not in env:
            full_env.pop(var, None)
    r = subprocess.run(
        [sys.executable, "-m", *cmd],
        input=json.dumps(payload),
        cwd=root,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, (cmd, r.stderr[-400:])
    return r.stdout


def _tree(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")}


def test_settings_hooks_cover_the_modules_we_expect() -> None:
    modules = {c[0] for c in SETTINGS_HOOKS}
    assert "harness_maker.telemetry" in modules
    assert "harness_maker.hooks.loop_gate" in modules
    assert "harness_maker.worktree" in modules


@pytest.mark.parametrize("cmd", SETTINGS_HOOKS, ids=lambda c: " ".join(c))
def test_every_settings_hook_is_silent_as_the_cursor_duplicate(
    tmp_path: Path, cmd: list[str]
) -> None:
    root = _marked_project(tmp_path)
    before = _tree(root)
    out = _run(cmd, root, _cursor_payload(root))
    assert out == ""
    assert _tree(root) == before


def test_telemetry_control_writes_as_the_cursor_copy(tmp_path: Path) -> None:
    """Same payload, same project — only the host marker differs, and now a row lands."""
    root = _marked_project(tmp_path)
    before = _tree(root)
    _run(["harness_maker.telemetry"], root, _cursor_payload(root), HM_HOOK_HOST="cursor")
    assert _tree(root) != before


@pytest.mark.parametrize("module", sorted({c[0] for c in SETTINGS_HOOKS}))
def test_every_settings_hook_module_checks_the_host(module: str) -> None:
    """A new `.claude/settings.json` hook without the check fires twice in Cursor again."""
    if module == "harness_maker.hooks.sessionid_envfile":
        pytest.skip("writes only to $CLAUDE_ENV_FILE, which Cursor never sets")
    path = SRC / Path(*module.split(".")).with_suffix(".py")
    assert "is_claude_copy_in_cursor" in path.read_text(encoding="utf-8")
