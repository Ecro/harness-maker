"""Retire a Cursor install left by 0.62 or earlier: warn once, delete only pristine files."""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from harness_maker.models import REMOVED_CURSOR_TARGET

CURSOR_DIR = ".cursor"
CURSOR_HOOKS_JSON = ".cursor/hooks.json"
_HOOKS_TOP_LEVEL = frozenset({"version", "hooks"})

# SPEC-hm-overhaul-p1 AC-002, verbatim. It repeats on every `make` while the file exists,
# because nothing else will tell the user the file has gone stale (IRR-001's pruned cache).
KEPT_TEXT = (
    "kept `{path}`: you edited it, so it was not deleted. harness-maker no longer maintains it "
    "and it will not be updated. Its hook commands point at this plugin version's cache path "
    "and stop working once that cache is pruned. Remove it when you are done with it."
)


def kept_warning(rel_path: str) -> str:
    return "WARN: " + KEPT_TEXT.format(path=rel_path)


def target_requested(disk_yaml: Mapping[str, Any], targets_flag: str | None) -> bool:
    """Did this run's inputs name the removed target, in the on-disk yaml or the flag?

    Read from the raw inputs because every parser drops the value before a `Target` exists,
    and both inputs together must still give one warning, not two.
    """
    raw = disk_yaml.get("targets")
    on_disk = isinstance(raw, list) and REMOVED_CURSOR_TARGET in raw
    flagged = targets_flag is not None and REMOVED_CURSOR_TARGET in {
        t.strip() for t in targets_flag.split(",")
    }
    return on_disk or flagged


CURSOR_MCP_JSON = ".cursor/mcp.json"


def removed_warning(targets: Sequence[str], *, had_cursor_mcp: bool = False) -> str:
    """The one line a `make` prints when its inputs still name the cursor target.

    With a `.cursor/mcp.json` on disk it also says where `mcp_servers` render now: only the
    codex target's `.codex/config.toml` (no other target renders an MCP file).
    """
    line = (
        "WARN: cursor target removed — harness-maker no longer renders .cursor/ (0.63.0); "
        f"targets are now [{', '.join(targets)}]. Unedited .cursor/ files are deleted and edited "
        "ones are kept."
    )
    if had_cursor_mcp:
        line += (
            " MCP servers from harness.yaml now render only to .codex/config.toml "
            "(codex target); .cursor/mcp.json is no longer written."
        )
    return line


def agent_model_warnings(disk_yaml: Mapping[str, Any]) -> list[str]:
    """One line per agent whose override still sets the `cursor:` model."""
    raw = disk_yaml.get("agent_models")
    if not isinstance(raw, dict):
        return []
    return [
        f"WARN: agent_models.{name}.cursor no longer sets a Cursor model — the cursor target "
        "was removed. The key still loads, and with no `claude:` a tier alias in it still picks "
        "the Claude model as before; set `claude:` to choose this agent's model."
        for name, spec in raw.items()
        if isinstance(spec, dict) and spec.get(REMOVED_CURSOR_TARGET) is not None
    ]


_WITH_PATH = re.compile(r'--with "[^"]*"')
_SRC = '--with "<SRC>"'


def _shipped(module: str) -> str:
    """One command exactly as the 0.62 Cursor template wrote it, its install path elided."""
    return (
        "HM_HOOK_HOST=cursor "
        'CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-$PWD}}" '
        f'PATH="$HOME/.local/bin:$PATH" uv run {_SRC} python -m {module}'
    )


# Frozen copy of every entry `templates/cursor/hooks.json.j2` could ship at db19f023 (0.62),
# per event: the whole entry, every key and value. Frozen rather than read from git, because a
# user's machine has no history to read, and the template is gone. The spec_gate entry rendered
# only at block strictness; a file with or without it is still ours.
SHIPPED_062: Mapping[str, tuple[Mapping[str, object], ...]] = {
    "preToolUse": (
        {"matcher": "Bash", "command": _shipped("harness_maker.hooks.loop_gate --mode pretooluse")},
        {"matcher": "Bash", "command": _shipped("harness_maker.gates.permission_gate")},
        {
            "matcher": "Write|Edit|MultiEdit",
            "command": _shipped("harness_maker.gates.worktree_gate"),
        },
        {"matcher": "Write|Edit|MultiEdit", "command": _shipped("harness_maker.gates.spec_gate")},
    ),
    "postToolUse": ({"matcher": "*", "command": _shipped("harness_maker.telemetry")},),
    "stop": ({"command": _shipped("harness_maker.telemetry")},),
    "sessionStart": ({"command": _shipped("harness_maker.hooks.autopilot_autoarm")},),
    "preCompact": ({"command": _shipped("harness_maker.hooks.flush_session"), "timeout": 30},),
}


def _is_shipped_entry(event: str, entry: object) -> bool:
    """The entry is one 0.62 shipped for `event`, byte for byte bar the install path.

    Anything else is the user's: an appended command, a re-scoped matcher, a changed or added
    timeout, an extra key. Identity on the module name alone (what the 0.62 merge used) would
    call a re-scoped gate "ours" and delete the user's scoping with it.
    """
    if not isinstance(entry, dict):
        return False
    command = entry.get("command")
    if not isinstance(command, str):
        return False
    normalized = {**entry, "command": _WITH_PATH.sub(_SRC, command, count=1)}
    return any(normalized == dict(shipped) for shipped in SHIPPED_062.get(event, ()))


def hooks_json_is_pristine(raw: bytes, recorded: set[str]) -> bool:
    """The manifest recorded these bytes AND every entry in them is one 0.62 shipped.

    A 0.62 `make --update` merged user entries into this file and recorded the MERGED hash,
    so the hash alone proves only that we wrote it (PLAN-hm-overhaul-p1-c ADR-004).
    """
    if hashlib.sha256(raw).hexdigest() not in recorded:
        return False
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict) or set(data) != _HOOKS_TOP_LEVEL or data["version"] != 1:
        return False
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    return all(
        isinstance(entries, list) and all(_is_shipped_entry(event, e) for e in entries)
        for event, entries in hooks.items()
    )


def symlink_kept_warning(rel_path: str) -> str:
    return f"WARN: kept `{rel_path}`: it is reached through a symlink, so it was not deleted."


def safe_to_delete(project_root: Path, rel_path: str) -> bool:
    """The path really lives under `<root>/.cursor`, reached through no symlink.

    A `.cursor` (or `.cursor/rules`) that is a symlink points the deletion somewhere the
    harness never rendered, possibly outside the project; refusing costs one leftover file.
    """
    base = project_root / CURSOR_DIR
    path = project_root / rel_path
    node = path
    while True:
        if node.is_symlink():
            return False
        if node == base:
            break
        if node == node.parent or base not in node.parents:
            return False
        node = node.parent
    try:
        return path.resolve().is_relative_to(base.resolve())
    except OSError:
        return False


def retire_hooks_json(project_root: Path, recorded: set[str]) -> str | None:
    """The only deletion path for `.cursor/hooks.json`; the orphan sweep never touches it.

    Returns the line to print, or None when there is no file. With no manifest record the
    harness has no evidence it wrote the file (a hand-made one, or a pre-manifest 0.5x render),
    so it gets the sweep's generic line, never the "you edited it" text.
    """
    path = project_root / CURSOR_HOOKS_JSON
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not recorded:
        return f"WARN: orphan-sweep KEPT {CURSOR_HOOKS_JSON} (theirs) — manual review needed"
    if not hooks_json_is_pristine(raw, recorded):
        return kept_warning(CURSOR_HOOKS_JSON)
    if not safe_to_delete(project_root, CURSOR_HOOKS_JSON):
        return symlink_kept_warning(CURSOR_HOOKS_JSON)
    try:
        path.unlink()
    except OSError as exc:
        return f"WARN: could not delete {CURSOR_HOOKS_JSON}: {exc}"
    return f"  RETIRED: {CURSOR_HOOKS_JSON} (pristine; the cursor target was removed)"


def remove_empty_dirs(project_root: Path) -> None:
    """Remove `.cursor/rules/` and `.cursor/` once nothing is left in them."""
    for rel in (".cursor/rules", CURSOR_DIR):
        if (project_root / rel).is_symlink():
            continue
        with contextlib.suppress(OSError):
            (project_root / rel).rmdir()
