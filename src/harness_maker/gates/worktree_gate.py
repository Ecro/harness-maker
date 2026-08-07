"""worktree_gate hook — refuse to write into ANOTHER session's worktree.

PLAN-multisession-marker-scoping ADR-004 replaced this gate's rule. It used to be a
self-confinement gate: union every `.hm-loop-*` marker's paths and block anything outside
that union. That rule has no empty-union case — a session with no worktree of its own has
an empty union, so it either blocks every write in the repo or, bypassed, lets base
sessions write freely into peers' worktrees. It was also session-BLIND: a leftover marker
from a DEAD session blocked an unrelated peer's every `Write`, `/tmp` included, while the
per-task worktree model — the default under `worktree.enabled: true` — had no marker at
all and therefore zero enforcement. The gate fired for the model not in use and stayed
silent for the one that was.

The rule now: **block a write iff the target is inside another LIVE session's worktree.**
Everything else is allowed — the base repo, and everything outside it.

Partition — THREE buckets, not two. Every marker falls in exactly one:

| Bucket         | Test                                            | Effect          |
|----------------|-------------------------------------------------|-----------------|
| mine           | header == my `session_id`, **or my cwd is in it** | never blocks me |
| peer           | header is a NON-EMPTY id != mine                | blocks me       |
| unattributable | header is EMPTY                                 | ignored         |

The third bucket is load-bearing. `worktree.create` writes a loop marker for every caller,
but only `loop.md.j2` passes `--claude-session-id`, so a standalone `/hm:execute`
worktree's marker has an empty header. Under a two-way partition "not mine" means peer,
and every standalone execute session would be blocked from its OWN worktree — a total work
stoppage. Ignoring the bucket is the deliberate trade: those worktrees get no peer
protection, consistent with ADR-006's rule that unattributable state is never enforced.

Precedence — own membership wins: block iff the path is in some peer's set and NOT in mine.

**Membership has two sources, and the cwd one is load-bearing (review rounds 1-2).** A
worktree is MINE if its marker header carries my id **or if my cwd is inside it**. Header
membership alone was not enough: ADR-010 keys a task marker by worktree with a single owner
header, so `mine ∩ peers` is always empty for that family and the header rule degenerates to
"whoever claimed it last owns it" — and a claim record is not an access-control list.
Trying to fix that at the WRITER failed in both directions within one round: refusing to
rewrite a stale header locked the resuming session out of its own task (a new session id
every day, so the ordinary path, and the block message's remedy was the very no-op that
caused it), while rewriting it let an id-less caller strip a live peer's protection. The cwd
answers a different and better question — not "who claimed this" but "who is standing in
it" — and no marker can be wrong about it.

Peer protection is unchanged: a session whose cwd is NOT inside a peer's worktree still
cannot write there, which is the drift this gate exists to stop.

ADR-006 — fail open, absolutely. No `session_id` in the payload (Cursor, Codex, any host
that does not send one) allows the write. This fires BEFORE any marker is read and nothing
overrides it. Enforcement here was prompt-level to begin with, so this is a floor that did
not exist rather than a wall removed.

ADR-004 accepted cost: **a drifting agent is no longer confined to its own worktree.** The
gate's original stated purpose — the technical enforcement layer for `<WT>` substitution —
is partly traded away. That was chosen knowingly; self-confinement is recoverable later as
an opt-in.

NON-GOALS: Bash-driven writes (`>`, `sed -i`, `python -c`) are not gated — `permission_gate`
owns dangerous-Bash vetting. Out-of-repo writes stay allowed, including the `mktemp -t` path
`wrapup.md.j2` writes a wiki body to.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# stdlib-only module (hashlib / re / pathlib) — safe to import at module scope on a hook
# that fires for every Write/Edit. `harness_maker.autopilot` is NOT: it would drag in
# pydantic and the 5k-line `worktree` module onto that latency path.
from harness_maker import loop_marker

# Tool names that can mutate files. Bash is intentionally omitted — blocking
# `git commit` or test runs would be too aggressive; permission_gate already
# vets dangerous bash patterns.
_GUARDED_TOOLS: frozenset[str] = frozenset({"Write", "Edit", "MultiEdit"})

#: Both marker families. `.hm-task-*` (ADR-008/010) is what gives the per-task worktree
#: model any session-attributable record at all; before it, that model had zero
#: enforcement here.
_MARKER_GLOBS: tuple[str, ...] = (loop_marker.MARKER_GLOB, ".hm-task-*")

#: Kept in sync with `worktree.WORKTREE_DIR_NAME` by
#: `tests/structural/test_gate_base_root_parity.py`. Duplicated rather than imported on
#: purpose: this hook runs on EVERY Write/Edit, and importing `harness_maker.autopilot`
#: (for `resolve_marker_root`) drags in pydantic and the 5k-line `worktree` module on a
#: latency path where this module currently needs only the stdlib.
_WORKTREE_DIR_NAME = ".worktrees"


def _payload_session_id(payload: dict[str, Any]) -> str | None:
    """The caller's sanitized Claude session id, or None when the host sends none.

    ADR-005: read from the PreToolUse payload, NOT from `HM_SESSION_ID` — that variable is
    written into `$CLAUDE_ENV_FILE` and sourced as an UNEXPORTED shell variable, so
    `os.environ` never sees it in a hook subprocess. The field name is a measured fact, not
    a code-reading inference: a temporary dump was inserted into `main()`, a real `Write`
    was issued, and the captured payload carried `session_id` (matching `HM_SESSION_ID`
    exactly) and NO `workspace` key. `runtime-env-gate-dead-on-arrival` is at count:2
    because a reviewer-approved argument about a runtime input was wrong twice.
    """
    raw = payload.get("session_id")
    if not isinstance(raw, str):
        return None
    return loop_marker.sanitize_session_id(raw.strip()) or None


def _strip_worktree(start: Path) -> Path:
    """Resolve a cwd to the directory the markers live under. Mirrors
    `autopilot.resolve_marker_root`: `.worktrees` strip FIRST, then a parent walk.

    ADR-005. Two ways to get this wrong, and both fail toward "found no markers, allowed
    everything" — silent, which is how this class of defect survives:

    * The payload `cwd` IS the worktree when a stage runs inside `.worktrees/<slug>`, so
      the strip is what lets the gate see the base `.claude/` at all.
    * The `cwd` is routinely a plain SUBDIRECTORY of the repo. Without the walk, the gate
      looks for `<repo>/src/.claude`, finds nothing, and allows every write in the project.

    The strip is checked BEFORE the walk because a git worktree carries its own `.git`
    sentinel and the walk would otherwise stop there. `.absolute()` and not `.resolve()`:
    the strip is positional on `.worktrees`, and `.resolve()` would canonicalise a
    symlinked worktree path and drop the component.
    """
    start = Path(start).absolute()
    parts = start.parts
    if _WORKTREE_DIR_NAME in parts:
        idx = len(parts) - 1 - parts[::-1].index(_WORKTREE_DIR_NAME)
        if idx > 0:
            base = Path(*parts[:idx])
            # Same strict sentinel as `autopilot._is_harness_root`: a task worktree's base
            # always owns the `.worktrees/`, so it is always a harness project. A bare
            # `.git` must NOT qualify — a git worktree carries one, and a parent/home repo
            # would otherwise capture resolution.
            if (base / ".claude" / "harness.yaml").is_file():
                return base
    for directory in (start, *start.parents):
        if (directory / ".claude" / "harness.yaml").is_file() or (directory / ".git").exists():
            return directory
    return start


def _raw_cwd(payload: dict[str, Any]) -> Path:
    """The tool's OWN working directory, before any `.worktrees` strip.

    Kept separate from `_project_root` (review round 1, CX-1). A relative `file_path` is
    resolved by the tool against THIS directory, so resolving it against the stripped base
    instead turns `../their-task/f.py` — which really lands in a peer's worktree — into a
    path outside the repo, and the gate allows it. Both a false-allow and a false-block are
    constructible. The branch is close to unreachable in Claude Code (the captured payload
    carries an absolute `file_path`), which is why it is a latent bug rather than a shipped
    hole — but the two roots are genuinely different things and conflating them was the
    defect.
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


def _project_root(payload: dict[str, Any]) -> Path:
    """The BASE project root — where the markers live. `_raw_cwd` with the worktree stripped."""
    return _strip_worktree(_raw_cwd(payload))


def _read_markers(project_root: Path) -> list[tuple[str, list[Path]]]:
    """`(session_id, live worktree paths)` for every readable marker in BOTH families.

    Existing directories only: a marker naming a worktree that is gone protects nothing,
    and honouring it would let an abandoned task lock a peer out of a path that no longer
    exists. The `claude_session_id:` header is dropped from the path list by
    `parse_marker_paths`'s `startswith("/")` rule — never by existence — so it can never be
    mistaken for a worktree path.
    """
    claude_dir = project_root / ".claude"
    if not claude_dir.is_dir():
        return []
    out: list[tuple[str, list[Path]]] = []
    for glob in _MARKER_GLOBS:
        for marker in sorted(claude_dir.glob(glob)):
            if not marker.is_file():
                continue
            try:
                text = marker.read_text(encoding="utf-8")
            except OSError:
                continue
            live = [
                p for p in (Path(s) for s in loop_marker.parse_marker_paths(text)) if p.is_dir()
            ]
            if live:
                out.append((loop_marker.parse_marker_session_id(text), [p.resolve() for p in live]))
    return out


def _peer_worktrees(project_root: Path, session_id: str, cwd: Path) -> list[Path]:
    """Worktrees owned by a DIFFERENT, identified session — the only paths we block.

    Empty-header markers are dropped entirely (the third bucket), and own membership wins
    over peer membership. Both rules are stated at module level; both are the difference
    between a gate and a work stoppage.
    """
    # `.resolve()`, not `.absolute()` — `is_relative_to` is a purely LEXICAL parts
    # comparison, and `_read_markers` stores `p.resolve()`d paths while `_target_path`
    # returns a `.resolve()`d target. A symlinked home or checkout, a `..` segment, or a
    # case-insensitive mount would make the two spellings differ, silently denying
    # self-membership and blocking a session from its own worktree — the exact failure this
    # rule exists to prevent, with no diagnostic. (The `.absolute()`-not-`.resolve()` note on
    # `_strip_worktree` is about the POSITIONAL `.worktrees` strip and does not transfer to a
    # membership test.) `strict=False` is the default, so a missing cwd does not raise.
    here = Path(cwd).resolve()
    mine: set[Path] = set()
    peers: set[Path] = set()
    for owner, paths in _read_markers(project_root):
        if not owner:
            continue
        for path in paths:
            # SELF-MEMBERSHIP BY CWD (review round 2, the fix for CR-1 + the P0 the first
            # attempt introduced). A worktree you are standing in is yours to write in,
            # whatever its marker header says. Marker attribution is a claim record, not an
            # access-control list, and using it as one produced two symmetric disasters:
            # refusing to rewrite a stale header locked the resuming session out of its own
            # task (a NEW session id every day, so the ordinary path), while rewriting it
            # let the least authenticated caller strip a live peer's protection. Neither is
            # fixable by choosing a better mutation rule, because "who claimed this" and
            # "who is working here" are different questions. This answers the second one
            # from a fact no marker can be wrong about.
            #
            # Peer protection is untouched: a session whose cwd is NOT inside a peer's
            # worktree still cannot write into it, which is the case the gate exists for
            # (a drifting agent editing someone else's tree from its own).
            if here == path or here.is_relative_to(path) or owner == session_id:
                mine.add(path)
            else:
                peers.add(path)
    return sorted(peers - mine)


def _target_path(payload: dict[str, Any], cwd: Path) -> Path | None:
    """The file the tool would write to, resolved to an absolute path.

    Both Claude Code and Cursor expose the target via ``tool_input.file_path``. A relative
    path is resolved against the tool's own ``cwd`` — NOT the stripped marker root, which
    is a different directory whenever the caller runs inside a worktree (CX-1).
    """
    raw = payload.get("tool_input")
    if not isinstance(raw, dict):
        return None
    candidate = raw.get("file_path") or raw.get("path")
    if not isinstance(candidate, str) or not candidate.strip():
        return None
    p = Path(candidate)
    if not p.is_absolute():
        p = cwd / p
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

    # ADR-006, BEFORE any marker is read: a caller we cannot identify is never constrained.
    session_id = _payload_session_id(payload)
    if session_id is None:
        return 0

    project_root = _project_root(payload)
    cwd = _raw_cwd(payload)
    peers = _peer_worktrees(project_root, session_id, cwd)
    if not peers:
        return 0

    target = _target_path(payload, cwd)
    if target is None:
        return 0  # missing/malformed input → allow (defensive)

    owner = next((wt for wt in peers if target.is_relative_to(wt)), None)
    if owner is None:
        return 0

    print(
        f"worktree_gate: write to {target} blocked — that path is inside ANOTHER "
        f"session's worktree ({owner}).\n"
        f"Concurrent sessions share this repo; writing into a peer's worktree corrupts "
        f"work it is about to commit.\n"
        f"Write to your own worktree or to the base repo instead. If that worktree is "
        f"abandoned, claim it first:\n"
        f"  uv run --with <plugin_path> python -m harness_maker.worktree "
        f"task-preflight <slug> <base> --claude-session-id <your-session-id>\n"
        f"That claims the task for you. Do NOT add --allow-shared-slug to force it: that "
        f"flag skips the live-peer check entirely, and if the owner is still working you "
        f"will evict each other in turn. If preflight reports the slug is held by a live "
        f"session, coordinate with it instead.\n"
        f'Note: Bash-driven writes (>, sed -i, python -c "open(...)") are NOT gated.',
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess
    sys.exit(main())
