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
import logging
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness_maker.hook_host import is_claude_copy_in_cursor
from harness_maker.loop_marker import (
    marker_dir_has_session,
    sanitize_session_id,
)

if TYPE_CHECKING:
    from harness_maker.autopilot import AutopilotMarker

# The autopilot modules (and pydantic under them) are imported lazily, inside the guarded
# check: an import failure must land in the fail-open handler, and the loop path and
# `--mode pretooluse` stay as light as they were before the check existed.


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


#: Above this the transcript is not read at all: the hook has a 10 s timeout.
_TRANSCRIPT_CAP_BYTES = 256 * 1024 * 1024
#: An authorization stamped further than this into the future is not credible (clock skew or a
#: crafted row) and is not treated as pending.
_FUTURE_SKEW = timedelta(minutes=5)
#: A peer marker counts as live only if its owner touched it this recently.
_PEER_IDLE_MINUTES = 30.0


def _autopilot_stop(
    data: dict[str, object], root: Path, session_id: str, now: datetime | None
) -> int:
    """Refuse the stop once when this turn authorized a stage it never invoked; else 0.

    Only a valid-id session reaches this (PLAN ADR-002): an id-less one shares the degraded
    marker, so ownership cannot be shown. Fails open on every read error, because a refusal
    built on a misread is exactly the every-turn block that got the first backstop deleted.

    The `harness_maker.autopilot` logger is silenced for the duration: a foreign or stale
    marker logs a warning there, and in the hook process that would be a second stderr line.
    """
    autopilot_logger = logging.getLogger("harness_maker.autopilot")
    was_disabled = autopilot_logger.disabled
    autopilot_logger.disabled = True
    try:
        stage = _unstarted_stage(data, root, session_id, now)
    except _FailOpenError as exc:
        _warn(str(exc))
        return 0
    except Exception as exc:  # noqa: BLE001 — a Stop hook must never crash the turn's end
        _warn(f"autopilot stop check skipped ({type(exc).__name__}: {exc})")
        return 0
    finally:
        autopilot_logger.disabled = was_disabled
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
    """``(stage, task_slug)`` of the latest authorization this turn left unstarted, or None.

    NOT read-only: `autopilot.active_marker` loads through `autopilot.load`, which performs
    the one-shot ADR-003 takeover of a pre-upgrade `.claude/.hm-autopilot` owned by this
    session. That is the same migration every other marker reader triggers.
    """
    from harness_maker import autopilot, autopilot_ledger
    from harness_maker.models import GATED_LEVEL

    moment = now if now is not None else datetime.now(UTC)
    base = autopilot.resolve_marker_root(root)
    marker = autopilot.active_marker(base, now=now, session_id=session_id)
    if marker is None or marker.level == GATED_LEVEL:
        return None
    if _peer_armed(base, session_id, moment):
        # The ledger is shared and not session-scoped: a live peer's rows look like ours.
        return None
    pending: dict[str, datetime] = {}
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
        if parsed > moment + _FUTURE_SKEW:
            continue
        pending[stage.value] = parsed
    if not pending:
        return None
    refusable = _scan_transcript(data, pending)
    if not refusable:
        return None
    latest = max(refusable, key=lambda name: pending[name])
    return latest, marker.task_slug


def _peer_armed(base: Path, session_id: str, moment: datetime) -> bool:
    """True when another session holds a live autopilot marker (PLAN ADR-006).

    Live = parseable, id-bearing, not `gated`, and touched within `_PEER_IDLE_MINUTES`
    (`last_seen`), or still TTL-fresh when it predates `last_seen`. An abandoned marker
    must not switch the gate off for the rest of its 18 h TTL.
    """
    from pydantic import ValidationError

    from harness_maker import autopilot
    from harness_maker.models import GATED_LEVEL

    for name in autopilot.other_keyed_markers(base, session_id=session_id):
        try:
            peer: AutopilotMarker = autopilot.AutopilotMarker.model_validate(
                json.loads((base / ".claude" / name).read_text(encoding="utf-8")), strict=False
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            continue
        if not peer.claude_session_id or peer.level == GATED_LEVEL:
            continue
        if peer.last_seen:
            idle = autopilot.idle_minutes(peer, now=moment)
            if idle is not None and idle <= _PEER_IDLE_MINUTES:
                return True
        elif autopilot._freshness(peer.created_at, moment) == "fresh":
            return True
    return False


def _scan_transcript(data: dict[str, object], pending: dict[str, datetime]) -> set[str]:
    """The pending stages the transcript shows neither started nor moved past (ADR-004).

    Streams the file and stops as soon as every stage has moved on. A transcript with no
    Claude Code record raises `_FailOpenError`: a foreign format must not read as "never
    invoked".
    """
    raw_path = data.get("transcript_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise _FailOpenError("Stop payload has no transcript_path; autopilot stop check skipped")
    open_stages = set(pending)
    seen_claude_record = False
    try:
        with open(raw_path, encoding="utf-8", errors="replace") as handle:
            size = os.fstat(handle.fileno()).st_size
            if size > _TRANSCRIPT_CAP_BYTES:
                raise _FailOpenError(
                    f"transcript is {size} bytes, over the cap; autopilot stop check skipped"
                )
            # Iterating a text file splits on newlines only — not on U+2028 inside a JSON
            # string, which `str.splitlines()` would.
            for line in handle:
                record = _parse_record(line)
                if record is None:
                    continue
                if record.get("type") in ("user", "assistant") and isinstance(
                    record.get("message"), dict
                ):
                    seen_claude_record = True
                for stage in list(open_stages):
                    if _moves_on(record, after=pending[stage], stage=stage):
                        open_stages.discard(stage)
                if not open_stages and seen_claude_record:
                    return set()
    except OSError as exc:
        raise _FailOpenError(
            f"transcript unreadable ({type(exc).__name__}); autopilot stop check skipped"
        ) from exc
    if not seen_claude_record:
        raise _FailOpenError("transcript has no Claude Code record; autopilot stop check skipped")
    return open_stages


def _parse_record(line: str) -> dict[str, Any] | None:
    if not line.strip():
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None


def _parse_instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _moves_on(record: dict[str, Any], *, after: datetime, stage: str) -> bool:
    """True when this record shows the stage started, or the person had the floor, after ``after``.

    Ambiguity reads as "moved on", which fails open: a user record or a queued command whose
    timestamp does not parse cannot be placed before the authorization.
    """
    if record.get("isSidechain"):
        return False
    kind = record.get("type")
    moment = _parse_instant(record.get("timestamp"))
    if kind == "attachment":
        inner = record.get("attachment")
        if not (isinstance(inner, dict) and inner.get("type") == "queued_command"):
            return False
        return moment is None or moment > after
    message = record.get("message")
    if kind not in ("user", "assistant") or not isinstance(message, dict):
        return False
    content = message.get("content")
    if kind == "assistant":
        return moment is not None and moment > after and _invokes(content, stage)
    if record.get("isMeta") or _only_tool_results(content):
        return False
    return moment is None or moment > after


def _invokes(content: object, stage: str) -> bool:
    """A `Skill` tool_use whose skill names ``stage``: `hm:x`, `/hm:x args`, `ns:x`, `hm-x`."""
    if not isinstance(content, list):
        return False
    pattern = re.compile(rf"(?:[\w.-]+:)*(?:hm[:-])?{re.escape(stage)}")
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        if block.get("name") != "Skill":
            continue
        tool_input = block.get("input")
        skill = tool_input.get("skill") if isinstance(tool_input, dict) else None
        if not isinstance(skill, str) or not skill.split():
            continue
        if pattern.fullmatch(skill.split()[0].removeprefix("/")):
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
