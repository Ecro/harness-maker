"""Block-level merge for marker-bearing files.

See ``docs/reference/block-merge-spec.md`` for the canonical spec. v1 supports
flat (non-nested) markers in markdown files only:

- ``<!-- @hm:user:<id> -->`` ... ``<!-- @hm:/user:<id> -->`` — user-owned region,
  KEEP across re-renders. Initial template ships placeholder content.
- ``<!-- @hm:block:<id> -->`` ... ``<!-- @hm:/block:<id> -->`` — template-owned
  region with optional drift-warning. REPLACE always; warn if user edited
  inside (detected via frontmatter ``blocks.<id>`` hash mismatch).

Free-floating content outside any marker is template-owned (REPLACE).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum

# ID syntax: optional underscore prefix (system-emitted ids like `_orphans`),
# then lowercase letter followed by 0..30 of [a-z0-9-].
_ID_PATTERN = r"_?[a-z][a-z0-9-]{0,30}"
_OPEN_RE = re.compile(rf"^[ \t]*<!--[ \t]*@hm:(block|user):({_ID_PATTERN})[ \t]*-->[ \t]*$")
_CLOSE_RE = re.compile(rf"^[ \t]*<!--[ \t]*@hm:/(block|user):({_ID_PATTERN})[ \t]*-->[ \t]*$")
_ANY_MARKER_RE = re.compile(r"<!--[ \t]*@hm:/?(?:block|user):")


class BlockKind(str, Enum):  # noqa: UP042 — pydantic-style (str, Enum) matches the rest of the codebase
    """Marker block ownership."""

    BLOCK = "block"
    USER = "user"


@dataclass(frozen=True)
class Segment:
    """One marker-delimited region in a parsed file."""

    kind: BlockKind
    id: str
    content: str  # body between open and close markers (inclusive of trailing \n on each line)


@dataclass
class MergeReport:
    """Surface to CLI: what the merge did to each block id."""

    user_blocks_preserved: list[str] = field(default_factory=list)
    user_blocks_seeded: list[str] = field(default_factory=list)  # NEW ids absent from OLD
    user_blocks_orphaned: list[str] = field(default_factory=list)  # OLD ids absent from NEW
    template_blocks_drifted: list[str] = field(default_factory=list)  # block:<id> user-edited


class ParseError(ValueError):
    """Raised on malformed markers (mismatched close, duplicate id, nested)."""


def has_markers(text: str) -> bool:
    """Cheap check — true if any ``@hm:(block|user):`` marker appears."""
    return _ANY_MARKER_RE.search(text) is not None


def parse_segments(text: str) -> list[Segment]:
    """Walk text and return all marker-delimited segments. Validates structure.

    Raises ParseError on: unclosed marker, mismatched close, duplicate id,
    nested markers (v1 prohibits any nesting).
    """
    lines = text.splitlines(keepends=True)
    segments: list[Segment] = []
    seen: set[tuple[BlockKind, str]] = set()
    i = 0
    n = len(lines)
    while i < n:
        bare = _strip_eol(lines[i])
        open_m = _OPEN_RE.match(bare)
        close_m = _CLOSE_RE.match(bare)
        if close_m and not open_m:
            msg = f"Unmatched close marker at line {i + 1}: {bare!r}"
            raise ParseError(msg)
        if open_m:
            kind = BlockKind(open_m.group(1))
            blk_id = open_m.group(2)
            key = (kind, blk_id)
            if key in seen:
                msg = f"Duplicate marker id @hm:{kind.value}:{blk_id} at line {i + 1}"
                raise ParseError(msg)
            close_idx = _find_close(lines, i + 1, kind, blk_id, open_line=i + 1)
            body = "".join(lines[i + 1 : close_idx])
            segments.append(Segment(kind=kind, id=blk_id, content=body))
            seen.add(key)
            i = close_idx + 1
            continue
        i += 1
    return segments


def parse_user_blocks(text: str) -> dict[str, str]:
    """Return ``{user_id: content}`` for every ``user:<id>`` block in text."""
    return {seg.id: seg.content for seg in parse_segments(text) if seg.kind == BlockKind.USER}


def block_hashes(text: str) -> dict[str, str]:
    """Return ``{block_id: sha256(content)}`` for every ``block:<id>`` in text.

    Used by reconcile to detect drift: a block:<id> whose body hash differs
    from the value stored in frontmatter ``blocks`` was edited by the user.
    """
    return {
        seg.id: hashlib.sha256(seg.content.encode("utf-8")).hexdigest()
        for seg in parse_segments(text)
        if seg.kind == BlockKind.BLOCK
    }


def merge(old_text: str, new_text: str) -> tuple[str, MergeReport]:
    """Produce merged text — NEW structure with OLD's ``user:<id>`` contents.

    Strategy:
      1. Validate both files (parse_segments).
      2. Walk NEW emitting verbatim. At each ``user:<id>`` open marker, swap
         the body for OLD's matching content if present; else keep NEW's seed.
      3. Append OLD ``user:<id>`` blocks not present in NEW as a single
         ``_orphans`` quarantine block at the end.

    The OLD file's ``block:<id>`` content is discarded (NEW always wins).
    Drift detection (``block:<id>`` user-edited) is reconcile's responsibility,
    not ours.
    """
    # Validate both sides — raises ParseError on malformed markers.
    parse_segments(old_text)
    parse_segments(new_text)

    old_user = parse_user_blocks(old_text)
    new_user_ids = {seg.id for seg in parse_segments(new_text) if seg.kind == BlockKind.USER}

    report = MergeReport()
    out: list[str] = []
    lines = new_text.splitlines(keepends=True)
    i = 0
    n = len(lines)
    while i < n:
        bare = _strip_eol(lines[i])
        open_m = _OPEN_RE.match(bare)
        if open_m and open_m.group(1) == "user":
            user_id = open_m.group(2)
            close_idx = _find_close(lines, i + 1, BlockKind.USER, user_id, open_line=i + 1)
            out.append(lines[i])  # open marker line
            if user_id in old_user:
                _emit_preserved(out, old_user[user_id])
                report.user_blocks_preserved.append(user_id)
            else:
                out.extend(lines[i + 1 : close_idx])  # NEW seed content
                report.user_blocks_seeded.append(user_id)
            out.append(lines[close_idx])  # close marker line
            i = close_idx + 1
            continue
        out.append(lines[i])
        i += 1

    orphan_ids = sorted(set(old_user) - new_user_ids)
    if orphan_ids:
        report.user_blocks_orphaned.extend(orphan_ids)
        out.append(_format_orphan_block(orphan_ids, old_user))

    return "".join(out), report


def detect_drift(old_text: str, frontmatter_blocks: dict[str, str]) -> list[str]:
    """Return list of ``block:<id>`` ids whose content hash differs from the
    frontmatter record (= user edited inside a template-owned block).

    Empty list when no drift. Pass an empty dict for ``frontmatter_blocks`` if
    the file has no recorded hashes (legacy).
    """
    current = block_hashes(old_text)
    drifted: list[str] = []
    for blk_id, recorded_hash in frontmatter_blocks.items():
        if blk_id in current and current[blk_id] != recorded_hash:
            drifted.append(blk_id)
    return sorted(drifted)


# ──────────────────────────────────────────────────────────────────────────────
# Internals
# ──────────────────────────────────────────────────────────────────────────────


def _strip_eol(line: str) -> str:
    return line.rstrip("\n").rstrip("\r")


def _find_close(
    lines: list[str],
    start: int,
    kind: BlockKind,
    blk_id: str,
    *,
    open_line: int,
) -> int:
    """Return the index of the matching close marker. v1 prohibits nesting —
    any open or non-matching close inside the range raises ParseError.
    """
    for j in range(start, len(lines)):
        bare = _strip_eol(lines[j])
        if _OPEN_RE.match(bare):
            msg = (
                f"Nested marker at line {j + 1} inside @hm:{kind.value}:{blk_id} "
                f"(open at line {open_line}); v1 forbids nesting"
            )
            raise ParseError(msg)
        close_m = _CLOSE_RE.match(bare)
        if not close_m:
            continue
        inner_kind, inner_id = close_m.group(1), close_m.group(2)
        if inner_kind == kind.value and inner_id == blk_id:
            return j
        msg = (
            f"Marker mismatch at line {j + 1}: expected @hm:/{kind.value}:{blk_id}, "
            f"found @hm:/{inner_kind}:{inner_id}"
        )
        raise ParseError(msg)
    msg = f"Unclosed marker @hm:{kind.value}:{blk_id} (open at line {open_line})"
    raise ParseError(msg)


def _emit_preserved(out: list[str], content: str) -> None:
    """Append OLD user content, ensuring it ends in a newline so the close
    marker sits on its own line.
    """
    if not content:
        return
    out.append(content)
    if not content.endswith("\n"):
        out.append("\n")


def _format_orphan_block(orphan_ids: list[str], old_user: dict[str, str]) -> str:
    parts = [
        "\n<!-- @hm:user:_orphans -->\n",
        "<!-- 이전 버전 user 블록인데 새 템플릿에 동명 id 없음. 수동 정리 필요. -->\n",
    ]
    for oid in orphan_ids:
        parts.append(f"\n## (orphan) {oid}\n\n")
        parts.append(old_user[oid])
        if not old_user[oid].endswith("\n"):
            parts.append("\n")
    parts.append("<!-- @hm:/user:_orphans -->\n")
    return "".join(parts)
