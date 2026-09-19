"""Read-only consumer for `.claude/memory/pending-proposals.md` — the backlog's first reader."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from harness_maker import command_registry

DEFAULT_BACKLOG = Path(".claude/memory/pending-proposals.md")

Status = Literal["open", "triaged"]

_OPEN_HEADING = re.compile(r"^##\s+Proposal:\s*(?P<name>.+?)\s*$")
_RESOLVED_HEADING = re.compile(r"^##\s+RESOLVED\b")
_ANY_HEADING = re.compile(r"^##\s+(?P<text>.+?)\s*$")
_TRAILING_DATE = re.compile(r"\s*\(\d{4}-\d{2}-\d{2}\)\s*$")
_HEADING_DATE = re.compile(r"\((?P<date>\d{4}-\d{2}-\d{2})\)\s*$")
_BACKTICKED = re.compile(r"`([^`]+)`")
#: A markdown table separator: every cell is dashes/colons/space.
_TABLE_SEPARATOR = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$")


@dataclass(frozen=True)
class ProposalSets:
    """The three buckets ADR-004 defines. `other_headings` is what makes the partition true."""

    open: list[str] = field(default_factory=list)
    triaged: list[str] = field(default_factory=list)
    other_headings: list[str] = field(default_factory=list)


def _proposal_name(heading_tail: str) -> str:
    """`alpha-guard (2026-01-03)` names the proposal `alpha-guard`."""
    return _TRAILING_DATE.sub("", heading_tail).strip()


def _first_cell(row: str) -> str:
    """Only column one names proposals; column two holds test paths, also backticked."""
    cells = row.strip().split("|")
    # `| a | b |` splits to ['', ' a ', ' b ', ''] — drop the outer empties.
    if len(cells) >= 3:
        return cells[1]
    return ""


def _triaged_names(body: str) -> list[str]:
    """Retired names live in table CELLS, not headings — there is no per-proposal heading."""
    names: list[str] = []
    in_table_body = False
    for line in body.splitlines():
        stripped = line.strip()
        if _TABLE_SEPARATOR.match(stripped):
            in_table_body = True
            continue
        if not stripped.startswith("|"):
            in_table_body = False
            continue
        if in_table_body:
            names.extend(_BACKTICKED.findall(_first_cell(stripped)))
    return names


def parse_proposals(text: str) -> ProposalSets:
    """Split a backlog into open / triaged / neither.

    The third bucket exists because AC-002's partition invariant is otherwise
    unsatisfiable: a `## Backlog note` heading is not a proposal in either state.
    """
    open_names: list[str] = []
    triaged: list[str] = []
    other: list[str] = []

    lines = text.splitlines()
    # Index every `## ` heading, then attribute the lines beneath it to that section.
    starts = [i for i, line in enumerate(lines) if _ANY_HEADING.match(line)]
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        heading = lines[start]
        body = "\n".join(lines[start + 1 : end])
        if (m := _OPEN_HEADING.match(heading)) is not None:
            name = _proposal_name(m.group("name"))
            if name:
                open_names.append(name)
            continue
        if _RESOLVED_HEADING.match(heading) is not None:
            triaged.extend(_triaged_names(body))
            continue
        other_m = _ANY_HEADING.match(heading)
        if other_m is not None:
            other.append(other_m.group("text"))

    # Dedupe while preserving order; a name retired in one batch and re-proposed later is
    # open, so open wins the tie — the file's most recent statement about it is the heading.
    open_unique = list(dict.fromkeys(open_names))
    triaged_unique = [n for n in dict.fromkeys(triaged) if n not in set(open_unique)]
    return ProposalSets(open=open_unique, triaged=triaged_unique, other_headings=other)


def _read(path: Path) -> str:
    """Absent backlog is not an error — a project may simply have none yet (absent-case rule)."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return ""


def oldest_open_date(text: str) -> str | None:
    """Earliest trailing `(YYYY-MM-DD)` among OPEN headings; None when none is dated.

    Only `## Proposal:` headings count — a RESOLVED batch heading carries a date too, and
    reading it would report a retired proposal's age as the backlog's (ADR-007).
    """
    dates = [
        m.group("date")
        for line in text.splitlines()
        if (heading := _OPEN_HEADING.match(line)) is not None
        and (m := _HEADING_DATE.search(heading.group("name"))) is not None
    ]
    return min(dates) if dates else None


def summarize_open(path: Path) -> dict[str, int | str | None]:
    """The one payload wrapup's main loop reads: `{"open": int, "oldest": date | None}`.

    An absent backlog is an empty state, not a failure (ADR-007) — a project that never
    escalated has no file, and 0 < 5 prints nothing.
    """
    text = _read(path)
    return {"open": len(parse_proposals(text).open), "oldest": oldest_open_date(text)}


def list_proposals(path: Path, status: Status) -> list[str]:
    sets = parse_proposals(_read(path))
    return sets.open if status == "open" else sets.triaged


def count_proposals(path: Path, status: Status) -> int:
    return len(list_proposals(path, status))


def _status_of(args: argparse.Namespace) -> Status:
    return "triaged" if args.triaged else "open"


def _add_status_flags(p: argparse.ArgumentParser) -> None:
    group = p.add_mutually_exclusive_group()
    group.add_argument("--open", action="store_true", help="unresolved proposals (default)")
    group.add_argument("--triaged", action="store_true", help="proposals a RESOLVED batch retired")
    p.add_argument("--file", type=Path, default=DEFAULT_BACKLOG, dest="file")


def main(argv: Sequence[str] | None = None) -> int:
    _guard = command_registry.guard_or_none("proposals", argv)
    if _guard is not None:
        return _guard
    parser = argparse.ArgumentParser(
        prog="hm proposals",
        description="Read .claude/memory/pending-proposals.md — the escalation backlog.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    # Spelled out rather than looped: `test_tc2_subparser_registry_matches_source_bidirectionally`
    # extracts subcommand names statically from `add_parser("<literal>")`, and a loop over a
    # tuple hides them — the registry would then claim two subcommands the source never shows.
    _add_status_flags(sub.add_parser("list", help="print one proposal name per line"))
    _add_status_flags(sub.add_parser("count", help="print a bare integer"))
    # Open-only by design (ADR-007): a status flag would put a triaged count under `open`.
    summary = sub.add_parser("summary", help='print {"open": N, "oldest": date|null} as JSON')
    summary.add_argument("--file", type=Path, default=DEFAULT_BACKLOG, dest="file")

    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (OSError, UnicodeDecodeError) as exc:
        # A backlog that exists but cannot be read is a failure, not an empty backlog —
        # reporting `open: 0` would hide exactly the file this reader exists to surface.
        # One line and a non-zero exit is what wrapup's degrade contract expects.
        sys.stderr.write(f"hm proposals: cannot read {args.file}: {exc}\n")
        return 1


def _run(args: argparse.Namespace) -> int:
    if args.command == "summary":
        sys.stdout.write(json.dumps(summarize_open(args.file)) + "\n")
        return 0
    status = _status_of(args)
    names = list_proposals(args.file, status)
    if args.command == "count":
        sys.stdout.write(f"{len(names)}\n")
        return 0
    for name in names:
        sys.stdout.write(f"{name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
