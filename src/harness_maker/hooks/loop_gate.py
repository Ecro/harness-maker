"""Loop gate hook — block session termination while THIS session's loop is active.

Session-scoped (PLAN-loop-marker-session-scoping): the Stop-hook reads its own
``session_id`` from the payload and blocks only when some
``.claude/.hm-loop-*`` marker's CONTENT header declares that id — so a parallel
idle session is never held open by another session's loop. A legacy global
``.hm-loop-active`` (written only on the degraded absent-id path, ADR-003) is
honored as a fallback so a content-less loop is still guarded.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from harness_maker.loop_marker import (
    marker_dir_has_session,
    sanitize_session_id,
)


def _project_root(data: dict[str, object]) -> Path:
    """Resolve project root payload-first (mirror worktree_gate._project_root).

    Order: payload ``workspace.current_dir`` → ``cwd`` → ``CLAUDE_PROJECT_DIR``
    → ``CURSOR_PROJECT_DIR`` → ``os.getcwd()`` (validator suggestion #5 — env-only
    resolution misroutes in multi-window / stripped environments).
    """
    raw_workspace = data.get("workspace")
    workspace = raw_workspace if isinstance(raw_workspace, dict) else {}
    cwd_val = data.get("cwd")
    candidate = (
        (workspace.get("current_dir") if isinstance(workspace, dict) else None)
        or (cwd_val if isinstance(cwd_val, str) else None)
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CURSOR_PROJECT_DIR")
        or os.getcwd()
    )
    root = Path(str(candidate))
    # If cwd is inside a harness worktree, step up to the project root so the
    # markers (which live at base ``.claude/``) are found.
    parts = root.parts
    if ".worktrees" in parts:
        idx = len(parts) - 1 - parts[::-1].index(".worktrees")
        if idx > 0:
            root = Path(*parts[:idx])
    return root


def _session_loop_active(root: Path, session_id: str) -> bool:
    """True iff some ``.claude/.hm-loop-*`` marker content declares ``session_id``."""
    return marker_dir_has_session(root / ".claude", session_id)


def _find_marker(start_dir: Path | None = None) -> Path | None:
    """Return .hm-loop-active from cwd, ancestors, or a harness worktree parent."""
    cwd = start_dir if start_dir is not None else Path.cwd()
    for directory in [cwd, *cwd.parents]:
        candidate = directory / ".hm-loop-active"
        if candidate.exists():
            return candidate
        git_marker = directory / ".git"
        if git_marker.exists():
            if git_marker.is_file():
                worktree_parent_marker = _worktree_parent_marker(directory)
                if worktree_parent_marker is not None:
                    return worktree_parent_marker
            break
    return None


def _worktree_parent_marker(directory: Path) -> Path | None:
    """Find the parent-repo loop marker for harness `.worktrees/<name>` dirs."""
    parts = directory.parts
    if ".worktrees" not in parts:
        return None
    idx = len(parts) - 1 - parts[::-1].index(".worktrees")
    if idx == 0:
        return None
    project_root = Path(*parts[:idx])
    candidate = project_root / ".hm-loop-active"
    return candidate if candidate.exists() else None


def _stop_hook(stdin_text: str) -> int:
    """Stop hook mode: block session termination while loop is active.

    stop_hook_active guard MUST be checked first — omitting it causes an
    infinite Stop event loop because the hook fires again after exit 2.
    """
    try:
        data: object = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[loop-gate] warn: invalid JSON stdin: {e}\n")
        data = {}

    if not isinstance(data, dict):
        data = {}
    if data.get("stop_hook_active"):
        return 0

    root = _project_root(data)

    # Primary: block iff a marker's content header matches THIS session's id.
    raw_sid = data.get("session_id")
    session_id = sanitize_session_id(raw_sid) if isinstance(raw_sid, str) else ""
    if _session_loop_active(root, session_id):
        response = {
            "decision": "block",
            "reason": (
                "/hm:loop is active for this session. To exit the loop early, "
                "remove this session's .claude/.hm-loop-* marker."
            ),
        }
        print(json.dumps(response))
        return 2

    # Fallback (ADR-003 H2 order): a legacy global .hm-loop-active guards a
    # DEGRADED (content-less) loop. Honor it ONLY when THIS session has no id of
    # its own — a session WITH a valid session_id relies solely on content-match,
    # so another session's degraded global cannot block it (re-review C1: the
    # unconditional global check re-opened cross-session interference for valid-id
    # sessions). Two both-degraded sessions still share the global — structurally
    # unavoidable without a per-session key (ADR-003 accepted limitation).
    if session_id:
        return 0
    marker = _find_marker(root)
    if marker is not None:
        response = {
            "decision": "block",
            "reason": (
                f"/hm:loop is active ({marker}). To exit the loop early: rm .hm-loop-active"
            ),
        }
        print(json.dumps(response))
        return 2

    return 0


def _pretooluse(stdin_text: str) -> int:  # noqa: ARG001
    """PreToolUse mode: advisory-only Cursor hook, always exits 0.

    Cursor has no Stop event equivalent. This hook injects a stderr reminder
    that the loop is active but never blocks tool use.
    """
    marker = _find_marker()
    if marker is not None:
        sys.stderr.write(f"[loop-gate] /hm:loop active ({marker}) — do not close this session.\n")
    return 0


def main() -> None:
    """Entry point for python -m harness_maker.hooks.loop_gate."""
    parser = argparse.ArgumentParser(description="Loop gate hook")
    parser.add_argument(
        "--mode",
        choices=["stop-hook", "pretooluse"],
        required=True,
    )
    args = parser.parse_args()

    stdin_text = sys.stdin.read() if not sys.stdin.isatty() else ""

    if args.mode == "stop-hook":
        sys.exit(_stop_hook(stdin_text))
    else:
        sys.exit(_pretooluse(stdin_text))


if __name__ == "__main__":
    main()
