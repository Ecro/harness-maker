"""Tell a hook whether it is the `.claude/settings.json` copy running inside Cursor."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path

# Prefixed onto every command the 0.62 `.cursor/hooks.json` shipped. Its presence in the
# hook's env says "I am the Cursor copy"; its presence on a command in the kept file says
# that command is a marked Cursor copy the Claude copy may defer to.
CURSOR_HOST_ENV = "HM_HOOK_HOST"
CURSOR_HOST_MARKER = f"{CURSOR_HOST_ENV}=cursor"


_WITH_ARG = re.compile(r"""--with\s+(?:"([^"]*)"|'([^']*)'|(\S+))""")
# A bare distribution name (`harness-maker`, `harness-maker==0.62.0`): uv resolves it from an
# index, so there is no path to check. Anything with a separator is a path and must exist.
_DIST_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[\w,.-]*\])?(?:[=<>!~]=?[\w.*+-]+)?")


def _commands(node: object) -> Iterator[str]:
    """Every `command` string anywhere in a parsed hooks file, whatever its nesting."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                yield value
            else:
                yield from _commands(value)
    elif isinstance(node, list):
        for item in node:
            yield from _commands(item)


def _with_target_is_live(command: str) -> bool:
    match = _WITH_ARG.search(command)
    if match is None:
        return False
    raw = next(g for g in match.groups() if g is not None)
    if _DIST_NAME.fullmatch(raw):
        return True
    expanded = os.path.expanduser(os.path.expandvars(raw))
    if "$" in expanded:
        return False
    return Path(expanded).exists()


def _cursor_runs_module(text: str, module: str) -> bool:
    """True when a marked command in `text` runs `module` and its `--with` target is live.

    Per hook, not per file: a file that merely mentions the marker somewhere, or runs other
    gates but not this one, or names a pruned plugin cache, leaves Cursor with no working copy
    of this hook, and the Claude copy is the only one left to run.
    """
    try:
        doc = json.loads(text)
    except ValueError:
        return False
    runs = re.compile(r"(?:^|\s)-m\s+" + re.escape(module) + r"(?=\s|$)")
    return any(
        CURSOR_HOST_MARKER in command and runs.search(command) and _with_target_is_live(command)
        for command in _commands(doc)
    )


def is_claude_copy_in_cursor(payload: Mapping[str, object] | str, module: str) -> bool:
    """True when this process is the Claude-settings copy of a hook Cursor already runs.

    Cursor imports `.claude/settings.json` hooks ("Include Third-Party Plugins, Skills, and
    Other Configs", on by default) and runs every matching hook from every source with no
    dedupe, all with the same Cursor payload. A kept 0.62 `.cursor/hooks.json` therefore
    makes each harness hook fire twice.

    `cursor_version` is in every payload Cursor sends and in none Claude Code sends, so a
    Claude Code session can never take this branch. `module` is the caller's own
    `python -m` name: the Claude copy stands down only when the kept file holds a marked,
    runnable command for that same module. Otherwise it runs, and says so on stderr, because
    a gate that defers to a copy that is not there is a gate that never runs.
    Takes the parsed payload or the raw stdin text, whichever the hook already holds.
    """
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload) if payload.strip() else {}
        except ValueError:
            return False
        if not isinstance(parsed, dict):
            return False
        payload = parsed
    if "cursor_version" not in payload or os.environ.get(CURSOR_HOST_ENV) == "cursor":
        return False
    root = os.environ.get("CURSOR_PROJECT_DIR")
    roots = payload.get("workspace_roots")
    if not root and isinstance(roots, list) and roots and isinstance(roots[0], str):
        root = roots[0]
    root = root or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        text = (Path(root) / ".cursor" / "hooks.json").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    if not text:
        return False
    if _cursor_runs_module(text, module):
        return True
    gate = module.rsplit(".", 1)[-1]
    print(
        f"[hook-host] Cursor copy of {gate} is stale or missing; running the Claude copy",
        file=sys.stderr,
    )
    return False
