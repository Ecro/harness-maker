"""Measure the pre-registered 28-day `[wiki:fact]` window (PLAN-mission-context-loop ADR-005).

`intent.yaml`'s `wiki_fact_entries_28d` outcome runs this. It answers exactly one pre-registered
question — how many subjects were captured as `[wiki:fact]` inside the window that starts on the
UTC date of the first `v*` release containing the `project-knowledge` skill — and refuses to
answer early, so wrapup 5.7's "measure now?" can never record a partial-window value.

Exit codes: 0 measured (the count is the last stdout line), 2 not released, 3 window open,
1 unexpected failure (git missing, not a repository).

Usage:
    uv run python scripts/measure_wiki_fact_window.py [--root .] [--now 2026-11-01T00:00:00Z]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

SKILL = "src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2"
WIKI = ".claude/memory/wiki.md"
WINDOW_DAYS = 28
_HEADING = re.compile(r"^## \[wiki:([a-z0-9-]+)\] (\S+) \| (\d{4}-\d{2}-\d{2})\s*$")
_FIRST_RECORDED = re.compile(r"\(first recorded (\d{4}-\d{2}-\d{2})\)")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=60, check=True
    ).stdout


def first_add_commit(root: Path) -> str | None:
    """The FIRST commit that added the skill — a later re-add must not move the anchor."""
    commits = _git(root, "log", "--diff-filter=A", "--format=%H", "--reverse", "--", SKILL).split()
    return commits[0] if commits else None


def release_tag(root: Path, commit: str) -> tuple[str, datetime] | None:
    """The earliest `v*` tag containing `commit`, by creator date — not by name or version sort."""
    out = _git(
        root,
        "tag",
        "--contains",
        commit,
        "--list",
        "v*",
        "--format=%(creatordate:iso-strict)\t%(refname:short)",
    )
    tags = []
    for line in out.splitlines():
        stamp, _, name = line.partition("\t")
        if stamp and name:
            tags.append((datetime.fromisoformat(stamp), name))
    if not tags:
        return None
    created, name = min(tags)
    return name, created


def _note(dates: dict[str, date], slug: str, day: str) -> None:
    parsed = date.fromisoformat(day)
    if slug not in dates or parsed < dates[slug]:
        dates[slug] = parsed


def _parse_wiki(text: str, dates: dict[str, date]) -> None:
    """Collect each fact slug's heading date and any `first recorded` date in its body.

    A correction re-dates the heading, so it carries the original capture date forward in its
    `Supersedes: … (first recorded <date>)` line; reading it keeps a capture that was corrected
    before it was ever committed inside the window it was made in.
    """
    slug: str | None = None
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            slug = heading.group(2) if heading.group(1) == "fact" else None
            if slug:
                _note(dates, slug, heading.group(3))
            continue
        if line.startswith("## ") or "@hm:/user:entries" in line:
            slug = None
            continue
        first = _FIRST_RECORDED.search(line) if slug else None
        if slug and first:
            _note(dates, slug, first.group(1))


def earliest_fact_dates(root: Path) -> dict[str, date]:
    """Each fact slug's earliest date across every committed version AND the working tree.

    Whole versions, not diff lines: a body line can only be attributed to its heading in
    context. The working tree matters because captures land in the base checkout uncommitted
    and are only folded into a commit at the next land.
    """
    dates: dict[str, date] = {}
    for sha in _git(root, "log", "--format=%H", "--", WIKI).split():
        try:
            _parse_wiki(_git(root, "show", f"{sha}:{WIKI}"), dates)
        except subprocess.CalledProcessError:
            continue  # the commit that deleted the file has no version to read
    wiki = root / WIKI
    if wiki.is_file():
        _parse_wiki(wiki.read_text(encoding="utf-8"), dates)
    return dates


def measure(root: Path, *, now: datetime) -> tuple[int, str]:
    commit = first_add_commit(root)
    tag = release_tag(root, commit) if commit else None
    if tag is None:
        return 2, "not released: no v* tag contains the project-knowledge skill yet"
    name, created = tag
    tag_day = created.astimezone(UTC).date()
    last_day = tag_day + timedelta(days=WINDOW_DAYS)
    today = now.astimezone(UTC).date()
    if today <= last_day:
        left = (last_day - today).days + 1
        return 3, f"window open ({left} days left): {name} {tag_day} .. {last_day}"
    count = sum(tag_day <= d <= last_day for d in earliest_fact_dates(root).values())
    return 0, f"{name} {tag_day} .. {last_day}\n{count}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--now", default=None, help="ISO-8601 instant (tests); default: now")
    args = parser.parse_args(argv)
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(tz=UTC)
    try:
        code, out = measure(args.root, now=now)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"measure failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(out, file=sys.stdout if code == 0 else sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
