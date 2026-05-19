"""Markdown retrieval for .claude/memory/{wiki,failures}.md → research/plan/spec stages.

Distinct from ``harness_maker.memory.retrieval.MemoryRetriever`` (JSONL 3-layer
episodic/semantic/profile store, ADR-002 MemMachine pattern). This module
parses the markdown wiki/failures index files and surfaces top-K relevant
entries to the stage-template-hosting Claude turn for inline semantic rerank.

PLAN-memory-md-operations Phase 1. The Python layer here owns deterministic
lexical pre-filtering only; semantic top-K selection happens prompt-natively
in the consuming Claude turn (see PLAN ADR-002 and ADR-005). No anthropic
API call from this module — that path replays the
`ship-without-verifying-target-env-credentials` failure mode.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from harness_maker.relevance import WORD_RE

# Sentinel for the fence-close substring; entry bodies containing this literal
# would otherwise let a malicious committer break out of the fence and feed
# post-fence text as instructions to the running Claude turn. Security review
# 2026-05-19 P1.
_FENCE_CLOSE = "</memory_candidates>"
_FENCE_CLOSE_NEUTRALIZED = "<\\/memory_candidates>"


_OPEN_MARKER = "<!-- @hm:user:entries -->"
_CLOSE_MARKER = "<!-- @hm:/user:entries -->"

# Strict 2-hash heading. 3+ hash headings (format drift from 0.15.x) are
# intentionally not parsed here — that is Approach A follow-up scope.
_HEADING_RE = re.compile(
    r"^##\s+\[(?P<tier>wiki|fail):(?P<category>[A-Za-z][A-Za-z0-9_-]*)\]\s+"
    r"(?P<slug>[A-Za-z0-9][A-Za-z0-9_-]*)\s+\|\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:\s+\|\s+count:(?P<count>\d+))?"
    r"\s*$"
)

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "or",
        "but",
        "the",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "is",
        "are",
        "be",
        "by",
        "as",
        "at",
        "how",
        "what",
        "why",
        "when",
        "where",
        "do",
        "does",
        "did",
        "can",
        "could",
        "should",
        "would",
        "will",
        "shall",
        "this",
        "that",
        "these",
        "those",
        "it",
        "we",
        "you",
        "i",
    }
)


@dataclass(frozen=True)
class MemoryEntry:
    tier: str
    category: str
    slug: str
    date: str
    count: int | None
    body: str
    source_path: str
    line_offset: int


def topic_tokens(topic: str) -> frozenset[str]:
    """Lowercase + stopword-strip topic tokens. Empty topic → empty frozenset."""
    if not topic:
        return frozenset()
    return frozenset(t.lower() for t in WORD_RE.findall(topic) if t.lower() not in _STOPWORDS)


def parse_entries(text: str, *, tier: str, source_path: str) -> list[MemoryEntry]:
    """Extract entries between @hm:user:entries / @hm:/user:entries markers.

    Permissive — duplicate slugs are NOT deduplicated. Surfaces both so the
    wrapup duplicate-section bug stays visible (PLAN ADR-006).
    """
    open_idx = text.find(_OPEN_MARKER)
    close_idx = text.find(_CLOSE_MARKER)
    if open_idx < 0 or close_idx < 0 or close_idx < open_idx:
        return []

    block_text = text[open_idx + len(_OPEN_MARKER) : close_idx]

    pre_text = text[: open_idx + len(_OPEN_MARKER)]
    open_marker_line = pre_text.count("\n") + 1
    body_first_line = open_marker_line + 1

    lines = block_text.splitlines()
    entries: list[MemoryEntry] = []

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = _HEADING_RE.match(line)
        if m:
            body_lines: list[str] = []
            j = i + 1
            while j < n and not _HEADING_RE.match(lines[j]):
                body_lines.append(lines[j])
                j += 1
            body = "\n".join(body_lines).strip("\n")
            count = int(m.group("count")) if m.group("count") else None
            entries.append(
                MemoryEntry(
                    tier=tier,
                    category=m.group("category"),
                    slug=m.group("slug"),
                    date=m.group("date"),
                    count=count,
                    body=body,
                    source_path=str(source_path),
                    line_offset=body_first_line + i,
                )
            )
            i = j
        else:
            i += 1

    return entries


def _entry_token_set(entry: MemoryEntry) -> frozenset[str]:
    parts = [
        entry.tier,
        entry.category,
        entry.slug,
        entry.date,
        str(entry.count) if entry.count is not None else "",
        entry.body,
    ]
    text = " ".join(parts).lower()
    return frozenset(WORD_RE.findall(text))


def score_entry(entry: MemoryEntry, topic_tokens_set: frozenset[str]) -> float:
    """Token-overlap score in [0, 1]. Mirrors relevance._keyword_score."""
    if not topic_tokens_set:
        return 0.0
    entry_tokens = _entry_token_set(entry)
    matched = sum(1 for t in topic_tokens_set if t in entry_tokens)
    return matched / len(topic_tokens_set)


def _date_desc_key(date: str) -> str:
    # Map ISO date to a string that sorts descending under asc sort.
    try:
        y, mo, d = date.split("-")
        return f"{9999 - int(y):04d}-{99 - int(mo):02d}-{99 - int(d):02d}"
    except (ValueError, IndexError):
        return "9999-99-99"


def top_candidates(
    entries: Sequence[MemoryEntry],
    topic: str,
    *,
    pre_k: int = 30,
) -> list[MemoryEntry]:
    """Lexical pre-filter. Returns up to pre_k entries by score desc.

    Tie-break: date desc, then slug asc. Entries with score 0 are filtered.
    Byte-cap enforcement is the caller's concern (see render_candidates_block).
    """
    tt = topic_tokens(topic)
    scored: list[tuple[float, MemoryEntry]] = []
    for e in entries:
        s = score_entry(e, tt)
        if s > 0.0:
            scored.append((s, e))
    scored.sort(key=lambda pair: (-pair[0], _date_desc_key(pair[1].date), pair[1].slug))
    return [e for _s, e in scored[:pre_k]]


def render_candidates_block(
    candidates: Sequence[MemoryEntry],
    topic: str,
    *,
    k: int = 6,
    pre_k: int = 30,
    byte_cap: int = 10240,
) -> str:
    """Emit the fenced markdown block per PLAN §Output schema.

    The instruction line is OUTSIDE the closing fence so the fence body is
    the data and the line is the directive to the running Claude turn.
    """
    instruction = (
        f"Surface the top-{k} candidates from the above block that are most "
        "semantically relevant to the topic. Reference each by its "
        "`[<tier>:<slug>]` anchor.\n"
    )

    # Escape topic before interpolation so a topic containing `"` or `>` cannot
    # break out of the fence attribute (security review P1, 2026-05-19).
    safe_topic = html.escape(topic, quote=True)
    fence_open = f'<memory_candidates topic="{safe_topic}" k="{k}" pre_k="{pre_k}">\n'
    fence_close = _FENCE_CLOSE + "\n"

    if not candidates:
        return fence_open + "(no entries matched)\n" + fence_close + instruction

    seen_slugs: dict[str, str] = {}

    def _heading(e: MemoryEntry, *, dup_annotation: str = "") -> str:
        count_part = f" | count:{e.count}" if e.count is not None else ""
        return f"## [{e.tier}:{e.category}] {e.slug} | {e.date}{count_part}{dup_annotation}"

    def _neutralize_fence(body: str) -> str:
        # Prevent a malicious entry body from closing the fence early
        # (security review P1, 2026-05-19).
        return body.replace(_FENCE_CLOSE, _FENCE_CLOSE_NEUTRALIZED)

    def _render_one(e: MemoryEntry) -> str:
        if e.slug in seen_slugs:
            dup = f" (duplicate of [{seen_slugs[e.slug]}:{e.slug}])"
        else:
            seen_slugs[e.slug] = e.tier
            dup = ""
        return f"{_heading(e, dup_annotation=dup)}\n{_neutralize_fence(e.body)}\n"

    rendered = [_render_one(e) for e in candidates]

    # Single-entry oversize → truncate body + sentinel, then re-check the cap
    # is actually satisfied (code review P1, 2026-05-19 — long topic + long
    # slug used to push final output past the cap).
    if len(rendered) == 1:
        out = fence_open + rendered[0] + fence_close + instruction
        if len(out.encode("utf-8")) <= byte_cap:
            return out
        e = candidates[0]
        # Account for actual fence + heading + instruction overhead rather
        # than a fixed 1KB reservation.
        body_bytes = _neutralize_fence(e.body).encode("utf-8")
        sentinel_template = "\n[... truncated {} bytes for byte-cap]\n"
        fixed_overhead = (
            len(fence_open.encode("utf-8"))
            + len(_heading(e).encode("utf-8"))
            + len(b"\n")
            + len(sentinel_template.format(99999).encode("utf-8"))
            + len(fence_close.encode("utf-8"))
            + len(instruction.encode("utf-8"))
        )
        max_body_bytes = max(byte_cap - fixed_overhead, 256)
        truncated_body = body_bytes[:max_body_bytes].decode("utf-8", errors="ignore")
        dropped = len(body_bytes) - len(truncated_body.encode("utf-8"))
        sentinel = sentinel_template.format(dropped)
        out = fence_open + f"{_heading(e)}\n{truncated_body}{sentinel}" + fence_close + instruction
        # Defensive: if our overhead accounting underestimated (extreme topic
        # length / unicode escape expansion), shrink the body further until
        # the cap holds. Bounded loop — at worst halves body each iter.
        while len(out.encode("utf-8")) > byte_cap and max_body_bytes > 256:
            max_body_bytes //= 2
            truncated_body = body_bytes[:max_body_bytes].decode("utf-8", errors="ignore")
            dropped = len(body_bytes) - len(truncated_body.encode("utf-8"))
            sentinel = sentinel_template.format(dropped)
            out = (
                fence_open
                + f"{_heading(e)}\n{truncated_body}{sentinel}"
                + fence_close
                + instruction
            )
        return out

    # Multi-entry: drop tail (lowest-scored) until under cap. Never mid-body
    # truncate.
    items = list(rendered)
    while items:
        body = "\n".join(items) + "\n"
        out = fence_open + body + fence_close + instruction
        if len(out.encode("utf-8")) <= byte_cap:
            return out
        items.pop()

    return fence_open + "(no entries matched)\n" + fence_close + instruction


def load_memory_dir(memory_dir: Path) -> list[MemoryEntry]:
    """Load wiki.md + failures.md entries from a memory dir."""
    if not memory_dir.is_dir():
        return []
    out: list[MemoryEntry] = []
    wiki = memory_dir / "wiki.md"
    failures = memory_dir / "failures.md"
    if wiki.is_file():
        out.extend(
            parse_entries(wiki.read_text(encoding="utf-8"), tier="wiki", source_path=str(wiki))
        )
    if failures.is_file():
        out.extend(
            parse_entries(
                failures.read_text(encoding="utf-8"),
                tier="fail",
                source_path=str(failures),
            )
        )
    return out


def _emit_error(args: argparse.Namespace, reason: str) -> None:
    sys.stderr.write(f"warning: memory_retrieve failed: {reason}\n")
    instruction = (
        f"Surface the top-{args.k} candidates from the above block that are most "
        "semantically relevant to the topic. Reference each by its "
        "`[<tier>:<slug>]` anchor.\n"
    )
    safe_topic = html.escape(args.topic, quote=True)
    # `reason` is internal (constructed from exception types / our own
    # f-strings), not user-controlled — no escape needed for the body line.
    sys.stdout.write(
        f'<memory_candidates topic="{safe_topic}" k="{args.k}" pre_k="{args.pre_k}">\n'
        f"(memory_retrieve failed: {reason}; falling back to first-60-lines context)\n"
        f"{_FENCE_CLOSE}\n" + instruction
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="harness_maker.memory_retrieve",
        description="Markdown memory loader for .claude/memory/{wiki,failures}.md",
    )
    parser.add_argument("--topic", required=True)
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--pre-k", type=int, default=30, dest="pre_k")
    parser.add_argument("--byte-cap", type=int, default=10240, dest="byte_cap")
    parser.add_argument(
        "--memory-dir", type=Path, default=Path(".claude/memory"), dest="memory_dir"
    )
    args = parser.parse_args(argv)

    try:
        if not args.memory_dir.is_dir():
            _emit_error(args, f"memory dir does not exist: {args.memory_dir}")
            return 0
        entries = load_memory_dir(args.memory_dir)
        ranked = top_candidates(entries, args.topic, pre_k=args.pre_k)
        out = render_candidates_block(
            ranked, args.topic, k=args.k, pre_k=args.pre_k, byte_cap=args.byte_cap
        )
        sys.stdout.write(out)
    except Exception as e:  # noqa: BLE001 — top-level graceful fallback per PLAN
        _emit_error(args, f"{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
