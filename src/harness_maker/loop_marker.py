"""Shared loop-marker content helpers — session-scoped /hm:loop parallelism.

Why a dedicated stdlib-only module: the loop-active marker
(``.claude/.hm-loop-{wt_name}``) is read/written by three consumers that must
agree byte-for-byte — ``worktree.py`` (producer + prune), ``hooks/loop_gate.py``
(Stop-hook, deliberately import-light), and ``hooks/sessionid_envfile.py``
(SessionStart). Renaming the filename to embed the Claude ``session_id`` would
break the existing storage contract (``_owned_session_uuids`` extracts the
worktree UUID from the filename suffix), so the Claude session id lives in the
marker *content* header instead (PLAN-loop-marker-session-scoping ADR-002/005).

The path-line parse rule is explicit (``startswith("/")``), never
existence-based — a header line is dropped by prefix, so it can never be
mistaken for a phantom worktree path (ADR-002, validator W1). ``session_id`` is
a hook-payload field and is sanitized before any filesystem use (ADR-006).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

#: Content header key carrying the (sanitized) Claude session id.
MARKER_HEADER_KEY = "claude_session_id"

#: Glob for per-session marker files under a project's ``.claude/`` dir.
MARKER_GLOB = ".hm-loop-*"

#: Tame session ids (UUID / hex forms) are used verbatim; anything else is
#: hashed. Bounds: 8..64 chars of hex digits and dashes.
_TAME_SESSION_ID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def sanitize_session_id(raw: str) -> str:
    """Return a filesystem-safe form of an external ``session_id`` (ADR-006).

    Empty stays empty (the absent-case signal). A tame UUID/hex id passes
    through verbatim; anything else (wrong length, path separators, control
    chars) is replaced by ``sha256(raw)[:16]`` so a hostile payload can never
    become a path fragment or a forged header.
    """
    if not raw:
        return ""
    if _TAME_SESSION_ID.fullmatch(raw):
        return raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def format_marker_content(claude_session_id: str, wt_paths: list[Path]) -> str:
    """Render marker content: a ``claude_session_id:`` header then absolute paths.

    The session id is sanitized here so every writer stores the canonical form.
    Path lines are always absolute, so readers can drop the header by prefix.
    A no-isolation marker passes ``wt_paths=[]`` → header only.
    """
    sanitized = sanitize_session_id(claude_session_id)
    lines = [f"{MARKER_HEADER_KEY}: {sanitized}"]
    lines.extend(str(p) for p in wt_paths)
    return "\n".join(lines) + "\n"


def parse_marker_session_id(text: str) -> str:
    """Extract the sanitized ``claude_session_id`` from marker content.

    Returns ``""`` for a legacy path-only marker (no header) or an empty header
    — both mean "no Claude session id recorded".
    """
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{MARKER_HEADER_KEY}:"):
            return stripped[len(MARKER_HEADER_KEY) + 1 :].strip()
        if stripped.startswith("/"):
            # Reached the path block without a header → legacy marker.
            break
    return ""


def parse_marker_paths(text: str) -> list[str]:
    """Return the absolute worktree path lines, dropping the header by prefix.

    The rule is ``startswith("/")`` — NOT existence-filtering — so a header line
    (or any non-path noise) can never be mistaken for a worktree path even if it
    happened to resolve on disk (validator W1).
    """
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("/"):
            out.append(stripped)
    return out


def marker_dir_has_session(claude_dir: Path, session_id: str) -> bool:
    """True iff some ``.claude/.hm-loop-*`` marker's content declares ``session_id``.

    Shared by the Stop-hook (loop_gate) and the loop-mode detection CLI so both
    use ONE content-match rule. Empty ``session_id`` → False (the loop signal is
    that ONLY a loop's ``worktree create`` passes ``--claude-session-id``; a bare
    worktree marker from a standalone /hm:execute has an empty header and so does
    NOT match — that is what distinguishes a loop from a plain worktree).
    """
    if not session_id or not claude_dir.is_dir():
        return False
    for marker in claude_dir.glob(MARKER_GLOB):
        if not marker.is_file():
            continue
        try:
            text = marker.read_text(encoding="utf-8")
        except OSError:
            continue
        if parse_marker_session_id(text) == session_id:
            return True
    return False
