"""Loop gate hook — block session termination while THIS session's loop is active.

Session-scoped (PLAN-loop-marker-session-scoping): the Stop-hook reads its own
``session_id`` from the payload and blocks only when some
``.claude/.hm-loop-*`` marker's CONTENT header declares that id — so a parallel
idle session is never held open by another session's loop. A legacy global
``.hm-loop-active`` (written only on the degraded absent-id path, ADR-003) is
honored as a fallback so a content-less loop is still guarded.

When no loop blocks, one autopilot check follows (SPEC-autopilot-stop-gate): a turn that
authorized a stage and never invoked it is refused once, naming the stage. Everything else —
and every read failure — falls through to the old answer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from harness_maker import autopilot, autopilot_ledger
from harness_maker.hook_host import is_claude_copy_in_cursor
from harness_maker.loop_marker import (
    marker_dir_has_session,
    sanitize_session_id,
)
from harness_maker.models import GATED_LEVEL


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


def _stop_hook(stdin_text: str, *, now: datetime | None = None) -> int:
    """Stop hook mode: block session termination while loop is active.

    stop_hook_active guard MUST be checked first — omitting it causes an
    infinite Stop event loop because the hook fires again after exit 2.

    ``now`` exists for tests: the marker's freshness window is 18 h, so a fixed-date fixture
    needs a fixed clock.
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
        return _autopilot_stop(data, root, session_id, now)
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


def _warn(message: str) -> None:
    sys.stderr.write(f"[loop-gate] warn: {message}\n")


def _autopilot_stop(
    data: dict[str, object], root: Path, session_id: str, now: datetime | None
) -> int:
    """Refuse the stop once when this turn authorized a stage it never invoked; else 0.

    Only a valid-id session reaches this (PLAN ADR-002): an id-less one shares the degraded
    marker, so ownership cannot be shown. Fails open on every read error, because a refusal
    built on a misread is exactly the every-turn block that got the first backstop deleted.
    """
    try:
        stage = _unstarted_stage(data, root, session_id, now)
    except _FailOpenError as exc:
        _warn(str(exc))
        return 0
    except Exception as exc:  # noqa: BLE001 — a Stop hook must never crash the turn's end
        _warn(f"autopilot stop check skipped ({type(exc).__name__}: {exc})")
        return 0
    if stage is None:
        return 0
    reason = _block_reason(stage[0], stage[1])
    print(json.dumps({"decision": "block", "reason": reason}))
    # Exit 2 makes Claude Code feed the model stderr, not stdout (PLAN ADR-008).
    sys.stderr.write(reason + "\n")
    return 2


class _FailOpenError(Exception):
    """A state the gate cannot judge; the message becomes the one warn line."""


def _unstarted_stage(
    data: dict[str, object], root: Path, session_id: str, now: datetime | None
) -> tuple[str, str | None] | None:
    """``(stage, task_slug)`` of the latest authorization this turn left unstarted, or None."""
    base = autopilot.resolve_marker_root(root)
    marker = autopilot.active_marker(base, now=now, session_id=session_id)
    if marker is None or marker.level == GATED_LEVEL:
        return None
    if _peer_armed(base, session_id, now):
        # The ledger is shared and not session-scoped: a peer's rows look like ours.
        return None
    pending: list[tuple[datetime, str]] = []
    for stage in marker.pipeline:
        row = autopilot_ledger.find_unconfirmed_authorization(
            base, to=stage.value, since=marker.created_at
        )
        if row is None:
            continue
        ts = row.get("ts")
        parsed = autopilot_ledger._parse_iso(ts) if isinstance(ts, str) else None
        if parsed is None:
            raise _FailOpenError(f"advance_authorized(to={stage.value}) has no parseable ts")
        pending.append((parsed, stage.value))
    if not pending:
        return None
    records = _transcript_records(data)
    refusable = [p for p in pending if not _turn_moved_on(records, after=p[0], stage=p[1])]
    if not refusable:
        return None
    return max(refusable)[1], marker.task_slug


def _peer_armed(base: Path, session_id: str, now: datetime | None) -> bool:
    """True when another session holds a fresh, id-bearing autopilot marker (PLAN ADR-006)."""
    for name in autopilot.other_keyed_markers(base, session_id=session_id):
        try:
            peer = autopilot.AutopilotMarker.model_validate(
                json.loads((base / ".claude" / name).read_text(encoding="utf-8")), strict=False
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            continue
        if peer.claude_session_id and autopilot._freshness(peer.created_at, now) == "fresh":
            return True
    return False


def _transcript_records(data: dict[str, object]) -> list[dict[str, Any]]:
    """The payload transcript's Claude Code records; `_FailOpenError` when there are none."""
    raw_path = data.get("transcript_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise _FailOpenError("Stop payload has no transcript_path; autopilot stop check skipped")
    try:
        text = Path(raw_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _FailOpenError(
            f"transcript unreadable ({type(exc).__name__}); check skipped"
        ) from exc
    records: list[dict[str, Any]] = []
    # `split("\n")`, not `splitlines()`: the latter also splits on U+2028 inside a JSON string.
    for line in text.split("\n"):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(record, dict)
            and record.get("type") in ("user", "assistant")
            and isinstance(record.get("message"), dict)
        ):
            records.append(record)
    if not records:
        # A foreign format must not read as "never invoked".
        raise _FailOpenError("transcript has no Claude Code record; autopilot stop check skipped")
    return records


def _turn_moved_on(records: list[dict[str, Any]], *, after: datetime, stage: str) -> bool:
    """True when, after ``after``, the stage was invoked or the person had the floor (ADR-004)."""
    for record in records:
        if record.get("isSidechain"):
            continue
        ts = record.get("timestamp")
        moment = autopilot_ledger._parse_iso(ts) if isinstance(ts, str) else None
        if moment is None or moment <= after:
            continue
        content = record["message"].get("content")
        if record.get("type") == "assistant":
            if _invokes(content, stage):
                return True
        elif not record.get("isMeta") and not _only_tool_results(content):
            return True
    return False


def _invokes(content: object, stage: str) -> bool:
    if not isinstance(content, list):
        return False
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        if block.get("name") != "Skill":
            continue
        tool_input = block.get("input")
        skill = tool_input.get("skill") if isinstance(tool_input, dict) else None
        if isinstance(skill, str) and skill.lstrip("/") == f"hm:{stage}":
            return True
    return False


def _only_tool_results(content: object) -> bool:
    return (
        isinstance(content, list)
        and bool(content)
        and all(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
    )


def _block_reason(stage: str, task_slug: str | None) -> str:
    args = f' and args "{task_slug}"' if task_slug else ""
    return (
        f"Autopilot authorized /hm:{stage} in this turn, but it was never invoked. "
        f'Run it now: call the Skill tool with skill "hm:{stage}"{args}. '
        "If you mean to stop here, ending the turn again stops: this hook refuses only once."
    )


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
    if is_claude_copy_in_cursor(stdin_text):
        sys.exit(0)

    if args.mode == "stop-hook":
        sys.exit(_stop_hook(stdin_text))
    else:
        sys.exit(_pretooluse(stdin_text))


if __name__ == "__main__":
    main()
