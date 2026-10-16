"""Retire a Cursor install left by 0.62 or earlier: warn once, delete only pristine files."""

from __future__ import annotations

import contextlib
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from harness_maker.hook_host import CURSOR_HOST_MARKER
from harness_maker.models import REMOVED_CURSOR_TARGET
from harness_maker.render import _normalize_hm_managed_command

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


def removed_warning(targets: Sequence[str]) -> str:
    return (
        "WARN: cursor target removed — harness-maker no longer renders .cursor/ (0.63.0); "
        f"targets are now [{', '.join(targets)}]. Unedited .cursor/ files are deleted and edited "
        "ones are kept."
    )


def agent_model_warnings(disk_yaml: Mapping[str, Any]) -> list[str]:
    """One line per agent whose override still sets the inert `cursor:` model."""
    raw = disk_yaml.get("agent_models")
    if not isinstance(raw, dict):
        return []
    return [
        f"WARN: agent_models.{name}.cursor is ignored — the cursor target was removed. "
        "The key still loads; set `claude:` to choose this agent's model."
        for name, spec in raw.items()
        if isinstance(spec, dict) and spec.get(REMOVED_CURSOR_TARGET) is not None
    ]


def _is_managed_entry(entry: object) -> bool:
    """A harness-rendered flat Cursor entry: host-marked, and a `harness_maker` command."""
    cmd = entry.get("command") if isinstance(entry, dict) else None
    return (
        isinstance(cmd, str)
        and cmd.startswith(CURSOR_HOST_MARKER + " ")
        and _normalize_hm_managed_command(cmd) != cmd
    )


def hooks_json_is_pristine(raw: bytes, recorded: set[str]) -> bool:
    """The manifest recorded these bytes AND nothing in them is the user's.

    A 0.62 `make --update` merged user entries into this file and recorded the MERGED hash,
    so the hash alone proves only that we wrote it (PLAN-hm-overhaul-p1-c ADR-004).
    """
    if hashlib.sha256(raw).hexdigest() not in recorded:
        return False
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict) or set(data) - _HOOKS_TOP_LEVEL:
        return False
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    return all(
        isinstance(entries, list) and all(_is_managed_entry(e) for e in entries)
        for entries in hooks.values()
    )


def retire_hooks_json(project_root: Path, recorded: set[str]) -> str | None:
    """The only deletion path for `.cursor/hooks.json`; the orphan sweep never touches it.

    Returns the line to print, or None when there is no file.
    """
    path = project_root / CURSOR_HOOKS_JSON
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not hooks_json_is_pristine(raw, recorded):
        return kept_warning(CURSOR_HOOKS_JSON)
    try:
        path.unlink()
    except OSError as exc:
        return f"WARN: could not delete {CURSOR_HOOKS_JSON}: {exc}"
    return f"  RETIRED: {CURSOR_HOOKS_JSON} (pristine; the cursor target was removed)"


def remove_empty_dirs(project_root: Path) -> None:
    """Remove `.cursor/rules/` and `.cursor/` once nothing is left in them."""
    for rel in (".cursor/rules", CURSOR_DIR):
        with contextlib.suppress(OSError):
            (project_root / rel).rmdir()
