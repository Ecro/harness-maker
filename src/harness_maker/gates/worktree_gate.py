"""worktree_gate hook — block Write/Edit/MultiEdit outside the active loop worktree.

Why: prompt-driven `<WT>` substitution (loop.md.j2 step 5) relies on Claude
faithfully prepending the worktree path to every Write/Edit/MultiEdit call.
Across 30 iters and a long context, drift is realistic — the LLM may forget
and start editing the main repo, defeating per-loop isolation. This gate is
the technical enforcement layer.

Mechanism:
- `harness_maker.worktree create` writes `.claude/.hm-loop-active` containing
  the absolute worktree path when isolation engages.
- `harness_maker.worktree finalize` removes the marker on matching WT.
- This gate fires PreToolUse on Write/Edit/MultiEdit; if marker present AND
  target file is outside the recorded worktree, exit 2 (block) with stderr
  guidance. If no marker (loop not active), no-op exit 0.

Default-on for both Claude Code and Cursor hook installs (rendered into
hooks.json.j2 templates). User can disable per-project by deleting the
PreToolUse worktree_gate entry from their hooks.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Tool names that can mutate files. Bash is intentionally omitted — blocking
# `git commit` or test runs would be too aggressive; permission_gate already
# vets dangerous bash patterns.
_GUARDED_TOOLS: frozenset[str] = frozenset({"Write", "Edit", "MultiEdit"})


def _project_root(payload: dict[str, Any]) -> Path:
    """Resolve project root, mirroring ``harness_maker.telemetry``'s order.

    Stdin payload wins over env vars — Claude Code includes
    ``workspace.current_dir``; Cursor includes ``cwd``. Env-only resolution
    misroutes when neither var is set (multi-window scenarios, stripped CI
    environments) — the gate would fall through to ``os.getcwd()`` of the
    hook subprocess, miss the marker, and silently allow drift writes.

    Order:
    1. ``payload.workspace.current_dir`` (Claude Code)
    2. ``payload.cwd`` (Cursor)
    3. ``CLAUDE_PROJECT_DIR`` env (compat alias)
    4. ``CURSOR_PROJECT_DIR`` env (Cursor-native)
    5. ``os.getcwd()`` (last resort)
    """
    raw_workspace = payload.get("workspace")
    workspace: dict[str, Any] = raw_workspace if isinstance(raw_workspace, dict) else {}
    cwd_str = (
        workspace.get("current_dir")
        or payload.get("cwd")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CURSOR_PROJECT_DIR")
        or os.getcwd()
    )
    return Path(cwd_str)


def _read_active_worktree(project_root: Path) -> Path | None:
    """Return the active loop's worktree path, or None when no loop is active.

    Marker is treated as advisory: missing file, unreadable, or pointing at a
    no-longer-existing path → return None (gate becomes a no-op). Better to
    miss enforcement than to hard-block the user when state is inconsistent.

    Race window: if the loop's `worktree finalize` runs between this gate's
    read and the user's actual tool call, the gate may briefly block a write
    against a worktree that no longer exists. The next tool call sees the
    cleared marker and allows. Sub-second window; acceptable.
    """
    marker = project_root / ".claude" / ".hm-loop-active"
    if not marker.is_file():
        return None
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    wt = Path(text)
    if not wt.is_dir():
        return None
    return wt.resolve()


def _target_path(payload: dict[str, Any], project_root: Path) -> Path | None:
    """Extract the file the tool would write to, resolved to an absolute path.

    Both Claude Code and Cursor expose the target via ``tool_input.file_path``.
    A relative path is resolved against ``project_root`` (best guess for the
    tool's cwd; absolute paths are passed through unchanged).
    """
    raw = payload.get("tool_input")
    if not isinstance(raw, dict):
        return None
    candidate = raw.get("file_path") or raw.get("path")
    if not isinstance(candidate, str) or not candidate.strip():
        return None
    p = Path(candidate)
    if not p.is_absolute():
        p = project_root / p
    return p.resolve()


def main() -> int:
    """Read PreToolUse JSON; exit 0 (allow) or 2 (block)."""
    try:
        text = sys.stdin.read()
        payload: Any = json.loads(text) if text.strip() else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_name = str(payload.get("tool_name") or "")
    if tool_name not in _GUARDED_TOOLS:
        return 0

    project_root = _project_root(payload)
    active_wt = _read_active_worktree(project_root)
    if active_wt is None:
        # No loop active — pass through unchecked.
        return 0

    target = _target_path(payload, project_root)
    if target is None:
        return 0  # missing/malformed input → allow (defensive)

    # If target is inside the active worktree, allow. relative_to raises
    # ValueError when the path is NOT a descendant of active_wt.
    try:
        target.relative_to(active_wt)
        return 0
    except ValueError:
        pass

    msg = (
        f"worktree_gate: write to {target} blocked — autoloop is active in "
        f"{active_wt}.\n"
        f"All Write/Edit/MultiEdit must target paths under {active_wt}/.\n"
        f"If you intended to edit main, finalize the loop first:\n"
        f"  uv run --with <plugin_path> python -m harness_maker.worktree "
        f"finalize {active_wt} <success|fail>\n"
        f'Note: Bash-driven writes (>, sed -i, python -c "open(...)") are '
        f"NOT gated. Always cd into the worktree for shell ops."
    )
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess
    sys.exit(main())
