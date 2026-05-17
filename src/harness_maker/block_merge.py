"""Block-level merge for marker-bearing files.

See ``docs/reference/block-merge-spec.md`` for the canonical spec. v1 supports
flat (non-nested) markers in markdown files only:

- ``<!-- @hm:user:<id> -->`` ... ``<!-- @hm:/user:<id> -->`` — user-owned region,
  KEEP across re-renders. Initial template ships placeholder content.
- ``<!-- @hm:block:<id> -->`` ... ``<!-- @hm:/block:<id> -->`` — template-owned
  region with optional drift-warning. REPLACE always; warn if user edited
  inside (detected via frontmatter ``blocks.<id>`` hash mismatch).
- ``<!-- @hm:harness:<id> -->`` ... ``<!-- @hm:/harness:<id> -->`` (Phase 6,
  ADR-009) — harness-owned region with INVERTED semantics: outside the
  marked region is user content (preserve byte-for-byte across re-render);
  inside is harness-managed (REPLACE). Used for foreign-config import where
  the user already owns the file and we mark only our generated sections.

Free-floating content outside any marker (when no ``@hm:harness:*`` is
present in the file) is template-owned (REPLACE).

Phase 6 (auto-fix): file-format-aware marker family. HTML comment markers
are the default for markdown/mdc; YAML/shell files use ``# @hm:...`` hash
markers; pure JSON files use a top-level ``_hm_harness`` key merge. The
dispatch is ``MarkerStyle`` selected via ``detect_marker_style(path)`` based
on file extension. WHY: ``continue_config.json`` and ``aider_conf.yml`` were
emitting templates whose marker syntax HTML-comment parser could not see,
producing silent no-op (apply appended duplicates on each call).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ID syntax: optional underscore prefix (system-emitted ids like `_orphans`),
# then lowercase letter followed by 0..30 of [a-z0-9-].
_ID_PATTERN = r"_?[a-z][a-z0-9-]{0,30}"
_OPEN_RE = re.compile(rf"^[ \t]*<!--[ \t]*@hm:(block|user|harness):({_ID_PATTERN})[ \t]*-->[ \t]*$")
_CLOSE_RE = re.compile(
    rf"^[ \t]*<!--[ \t]*@hm:/(block|user|harness):({_ID_PATTERN})[ \t]*-->[ \t]*$"
)
_ANY_MARKER_RE = re.compile(r"<!--[ \t]*@hm:/?(?:block|user|harness):")
# Hash-comment marker family (YAML / shell). Single ``#`` plus optional space,
# then ``@hm:<kind>:<id>`` for open and ``@hm:/<kind>:<id>`` for close. Leading
# whitespace permitted so indented YAML keys still match. Must not match
# double-hash ``##`` (markdown headings inside a hash-commented YAML body).
_HASH_OPEN_RE = re.compile(rf"^[ \t]*#[ \t]*@hm:(block|user|harness):({_ID_PATTERN})[ \t]*$")
_HASH_CLOSE_RE = re.compile(rf"^[ \t]*#[ \t]*@hm:/(block|user|harness):({_ID_PATTERN})[ \t]*$")
_ANY_HASH_MARKER_RE = re.compile(r"#[ \t]*@hm:/?(?:block|user|harness):")
# Fenced code block boundary — markdown ``` (optional info string).
# Validator W2 requires literal ``@hm:`` strings inside fenced code blocks to
# be skipped (no false-positive marker detection).
_FENCE_RE = re.compile(r"^[ \t]*```")

# Top-level JSON key used for the harness-owned region in pure JSON files
# (where HTML / hash comments are not valid syntax).
_JSON_HARNESS_KEY = "_hm_harness"


class MarkerStyle(str, Enum):  # noqa: UP042 — pydantic-style (str, Enum) matches the rest of the codebase
    """Marker syntax dispatch — per file format.

    HTML_COMMENT is the default for markdown / mdc; HASH_COMMENT is for
    YAML / shell where HTML comments would not be valid syntax to the
    downstream parser; JSON_KEY is for pure JSON where neither comment style
    is legal — we merge a single top-level ``_hm_harness`` key instead.
    """

    HTML_COMMENT = "html_comment"
    HASH_COMMENT = "hash_comment"
    JSON_KEY = "json_key"


class BlockKind(str, Enum):  # noqa: UP042 — pydantic-style (str, Enum) matches the rest of the codebase
    """Marker block ownership.

    HARNESS family (Phase 6, ADR-009) is ORTHOGONAL to BLOCK / USER — files
    can contain any combination. Inverted semantics: HARNESS-marked regions
    are template-owned (REPLACE); content outside HARNESS markers is
    user-owned (PRESERVE byte-for-byte).
    """

    BLOCK = "block"
    USER = "user"
    HARNESS = "harness"


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


class MarkerMismatchError(ParseError):
    """Phase 6 (W2): open/close pair kind or id mismatch — typed for callers
    that need to distinguish mismatched pairs from other parse failures.

    Subclass of ParseError so existing ``except ParseError:`` callers (e.g.
    reconcile.py) still catch this without source changes.
    """


class MarkerNestedError(ParseError):
    """Phase 6 (W2): nested markers detected. v1 forbids nesting; raise so
    the caller can surface a precise message rather than silent miscount.
    """


def detect_marker_style(path: Path) -> MarkerStyle:
    """Choose the marker style for a path by file extension.

    Why per-extension: the downstream parser (Cursor / Aider / Continue) only
    accepts its own native comment syntax. Pure JSON has no comment syntax at
    all, so we use a top-level key merge instead.
    """
    suffix = path.suffix.lower()
    if suffix == ".json":
        return MarkerStyle.JSON_KEY
    if suffix in {".yml", ".yaml"}:
        return MarkerStyle.HASH_COMMENT
    return MarkerStyle.HTML_COMMENT


def has_markers(text: str, style: MarkerStyle = MarkerStyle.HTML_COMMENT) -> bool:
    """Cheap check — true if any ``@hm:(block|user|harness):`` marker appears.

    Style-aware: HTML comment markers for default, hash markers for YAML,
    presence of top-level ``_hm_harness`` for JSON.
    """
    if style is MarkerStyle.HTML_COMMENT:
        return _ANY_MARKER_RE.search(text) is not None
    if style is MarkerStyle.HASH_COMMENT:
        return _ANY_HASH_MARKER_RE.search(text) is not None
    # JSON_KEY: try to parse; presence of the harness key counts as markers.
    try:
        parsed = json.loads(text) if text.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return False
    return isinstance(parsed, dict) and _JSON_HARNESS_KEY in parsed


def parse_segments(text: str, style: MarkerStyle = MarkerStyle.HTML_COMMENT) -> list[Segment]:
    """Walk text and return all marker-delimited segments. Validates structure.

    Raises ParseError on: unclosed marker, mismatched close, duplicate id,
    nested markers (v1 prohibits any nesting). Markers literally appearing
    inside markdown fenced code blocks (``` ... ```) are skipped — validator
    W2 requires no false-positive detection there.
    """
    if style is MarkerStyle.JSON_KEY:
        return _parse_segments_json(text)
    if style is MarkerStyle.HASH_COMMENT:
        open_re, close_re = _HASH_OPEN_RE, _HASH_CLOSE_RE
    else:
        open_re, close_re = _OPEN_RE, _CLOSE_RE
    lines = text.splitlines(keepends=True)
    segments: list[Segment] = []
    seen: set[tuple[BlockKind, str]] = set()
    i = 0
    n = len(lines)
    in_fence = False
    while i < n:
        bare = _strip_eol(lines[i])
        if style is MarkerStyle.HTML_COMMENT and _FENCE_RE.match(bare):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        open_m = open_re.match(bare)
        close_m = close_re.match(bare)
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
            close_idx = _find_close(lines, i + 1, kind, blk_id, open_line=i + 1, style=style)
            body = "".join(lines[i + 1 : close_idx])
            segments.append(Segment(kind=kind, id=blk_id, content=body))
            seen.add(key)
            i = close_idx + 1
            continue
        i += 1
    return segments


def _parse_segments_json(text: str) -> list[Segment]:
    """JSON_KEY style: the top-level ``_hm_harness`` value is the single
    virtual harness block (id = ``_hm_harness``). Any other top-level keys
    are treated as user content (preserved on merge).

    Raises ParseError if the document is not valid JSON or not an object.
    """
    stripped = text.strip()
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, ValueError) as e:
        msg = f"JSON marker file is not valid JSON: {e}"
        raise ParseError(msg) from e
    if not isinstance(parsed, dict):
        msg = f"JSON marker file must be a top-level object, got {type(parsed).__name__}"
        raise ParseError(msg)
    if _JSON_HARNESS_KEY not in parsed:
        return []
    body_value = parsed[_JSON_HARNESS_KEY]
    body = json.dumps(body_value, indent=2, sort_keys=True)
    return [Segment(kind=BlockKind.HARNESS, id=_JSON_HARNESS_KEY, content=body)]


def parse_user_blocks(text: str, style: MarkerStyle = MarkerStyle.HTML_COMMENT) -> dict[str, str]:
    """Return ``{user_id: content}`` for every ``user:<id>`` block in text."""
    return {
        seg.id: seg.content for seg in parse_segments(text, style) if seg.kind == BlockKind.USER
    }


def parse_harness_blocks(
    text: str, style: MarkerStyle = MarkerStyle.HTML_COMMENT
) -> dict[str, str]:
    """Return ``{harness_id: content}`` for every ``harness:<id>`` block (Phase 6)."""
    return {
        seg.id: seg.content for seg in parse_segments(text, style) if seg.kind == BlockKind.HARNESS
    }


def merge_inverted(
    old_text: str,
    new_text: str,
    style: MarkerStyle = MarkerStyle.HTML_COMMENT,
) -> tuple[str, MergeReport]:
    """Inverted-marker merge (ADR-009): preserve user content OUTSIDE
    ``@hm:harness:<id>`` regions byte-for-byte, REPLACE content INSIDE.

    Strategy:
      1. Validate both files via parse_segments (raises typed ParseError on
         mismatched/nested markers).
      2. Walk OLD line-by-line emitting verbatim — that's user-owned content.
         When an ``@hm:harness:<id>`` open marker is seen in OLD, emit the
         open marker, then replace the body with NEW's matching harness block
         body (if present), then emit the close marker. If NEW lacks that id,
         the OLD body is preserved (orphan — caller decides clean-up).
      3. For ``@hm:harness:<id>`` blocks present in NEW but absent in OLD
         (= first-time apply, fresh injection point), append them at the end
         of the merged file in the order NEW declares them.

    User ``@hm:user:<id>`` and ``@hm:block:<id>`` markers in OLD are passed
    through unchanged — they coexist orthogonally with the harness family.

    JSON_KEY style: top-level ``_hm_harness`` is the harness-owned region;
    all other top-level keys are user-owned and preserved.
    """
    if style is MarkerStyle.JSON_KEY:
        return _merge_inverted_json(old_text, new_text)

    parse_segments(old_text, style)
    parse_segments(new_text, style)

    new_harness = parse_harness_blocks(new_text, style)
    old_harness_ids: set[str] = {
        seg.id for seg in parse_segments(old_text, style) if seg.kind == BlockKind.HARNESS
    }

    report = MergeReport()
    out: list[str] = []
    lines = old_text.splitlines(keepends=True)
    i = 0
    n = len(lines)
    in_fence = False
    open_re = _HASH_OPEN_RE if style is MarkerStyle.HASH_COMMENT else _OPEN_RE
    while i < n:
        bare = _strip_eol(lines[i])
        if style is MarkerStyle.HTML_COMMENT and _FENCE_RE.match(bare):
            in_fence = not in_fence
            out.append(lines[i])
            i += 1
            continue
        if in_fence:
            out.append(lines[i])
            i += 1
            continue
        open_m = open_re.match(bare)
        if open_m and open_m.group(1) == "harness":
            harness_id = open_m.group(2)
            close_idx = _find_close(
                lines, i + 1, BlockKind.HARNESS, harness_id, open_line=i + 1, style=style
            )
            out.append(lines[i])  # open marker line
            if harness_id in new_harness:
                _emit_preserved(out, new_harness[harness_id])
                report.user_blocks_preserved.append(harness_id)
            else:
                # NEW dropped this id — keep OLD body so user doesn't lose
                # content unexpectedly. Caller can detect via report.
                out.extend(lines[i + 1 : close_idx])
                report.user_blocks_orphaned.append(harness_id)
            out.append(lines[close_idx])
            i = close_idx + 1
            continue
        out.append(lines[i])
        i += 1

    # Append NEW harness blocks absent from OLD — first-time injection.
    new_only_ids = [
        seg.id for seg in parse_segments(new_text, style) if seg.kind == BlockKind.HARNESS
    ]
    for nid in new_only_ids:
        if nid in old_harness_ids:
            continue
        if out and not out[-1].endswith("\n"):
            out.append("\n")
        if style is MarkerStyle.HASH_COMMENT:
            out.append(f"# @hm:harness:{nid}\n")
        else:
            out.append(f"<!-- @hm:harness:{nid} -->\n")
        _emit_preserved(out, new_harness[nid])
        if style is MarkerStyle.HASH_COMMENT:
            out.append(f"# @hm:/harness:{nid}\n")
        else:
            out.append(f"<!-- @hm:/harness:{nid} -->\n")
        report.user_blocks_seeded.append(nid)

    return "".join(out), report


def _merge_inverted_json(old_text: str, new_text: str) -> tuple[str, MergeReport]:
    """JSON_KEY merge: replace top-level ``_hm_harness`` value with NEW's;
    preserve every other top-level key from OLD.

    Stable key order: NEW's ``_hm_harness`` value is placed where OLD already
    had the key (or appended after user keys if absent). Other user keys keep
    OLD's order. Output formatted with ``indent=2`` for deterministic diffs.
    """
    report = MergeReport()
    stripped_old = old_text.strip()
    if stripped_old:
        try:
            old_parsed = json.loads(stripped_old, object_pairs_hook=OrderedDict)
        except (json.JSONDecodeError, ValueError) as e:
            msg = f"JSON marker file (OLD) is not valid JSON: {e}"
            raise ParseError(msg) from e
        if not isinstance(old_parsed, dict):
            msg = (
                "JSON marker file (OLD) must be a top-level object, "
                f"got {type(old_parsed).__name__}"
            )
            raise ParseError(msg)
    else:
        old_parsed = OrderedDict()

    stripped_new = new_text.strip()
    if stripped_new:
        try:
            new_parsed = json.loads(stripped_new, object_pairs_hook=OrderedDict)
        except (json.JSONDecodeError, ValueError) as e:
            msg = f"JSON marker file (NEW) is not valid JSON: {e}"
            raise ParseError(msg) from e
        if not isinstance(new_parsed, dict):
            msg = (
                "JSON marker file (NEW) must be a top-level object, "
                f"got {type(new_parsed).__name__}"
            )
            raise ParseError(msg)
    else:
        new_parsed = OrderedDict()

    old_has_key = _JSON_HARNESS_KEY in old_parsed
    new_has_key = _JSON_HARNESS_KEY in new_parsed

    merged: OrderedDict[str, Any] = OrderedDict()
    for key, value in old_parsed.items():
        if key == _JSON_HARNESS_KEY:
            if new_has_key:
                merged[key] = new_parsed[_JSON_HARNESS_KEY]
            else:
                # NEW dropped harness key — keep OLD's so user doesn't lose
                # state; mark as orphaned for caller awareness.
                merged[key] = value
                report.user_blocks_orphaned.append(_JSON_HARNESS_KEY)
        else:
            merged[key] = value

    if new_has_key and not old_has_key:
        merged[_JSON_HARNESS_KEY] = new_parsed[_JSON_HARNESS_KEY]
        report.user_blocks_seeded.append(_JSON_HARNESS_KEY)
    elif new_has_key and old_has_key:
        report.user_blocks_preserved.append(_JSON_HARNESS_KEY)

    return json.dumps(merged, indent=2) + "\n", report


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
    style: MarkerStyle = MarkerStyle.HTML_COMMENT,
) -> int:
    """Return the index of the matching close marker. v1 prohibits nesting —
    any open or non-matching close inside the range raises a typed
    ``MarkerNestedError`` or ``MarkerMismatchError`` (both subclass
    ``ParseError`` so legacy callers continue to work).

    Tracks fence state so markers literally appearing inside fenced code
    blocks are skipped (validator W2) — only relevant for HTML_COMMENT style.
    """
    open_re = _HASH_OPEN_RE if style is MarkerStyle.HASH_COMMENT else _OPEN_RE
    close_re = _HASH_CLOSE_RE if style is MarkerStyle.HASH_COMMENT else _CLOSE_RE
    # Walk forward from start; track fences scoped to this scan window. The
    # open marker itself cannot live inside a fence (caller skipped fence
    # lines) so start with in_fence = False.
    in_fence = False
    for j in range(start, len(lines)):
        bare = _strip_eol(lines[j])
        if style is MarkerStyle.HTML_COMMENT and _FENCE_RE.match(bare):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if open_re.match(bare):
            msg = (
                f"Nested marker at line {j + 1} inside @hm:{kind.value}:{blk_id} "
                f"(open at line {open_line}); v1 forbids nesting"
            )
            raise MarkerNestedError(msg)
        close_m = close_re.match(bare)
        if not close_m:
            continue
        inner_kind, inner_id = close_m.group(1), close_m.group(2)
        if inner_kind == kind.value and inner_id == blk_id:
            return j
        msg = (
            f"Marker mismatch at line {j + 1}: expected @hm:/{kind.value}:{blk_id}, "
            f"found @hm:/{inner_kind}:{inner_id}"
        )
        raise MarkerMismatchError(msg)
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
