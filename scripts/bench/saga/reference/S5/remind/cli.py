"""Command line: `python -m remind.cli add|list|import|done ...`."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from remind import api, ics
from remind.fmt import format_line

RED, RESET = "\x1b[31m", "\x1b[0m"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="remind")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="add a reminder")
    add.add_argument("text")
    add.add_argument("--due", help="due time, 'YYYY-MM-DD HH:MM' (UTC)")
    add.add_argument("--when", dest="due", help=argparse.SUPPRESS)  # old name, kept for scripts
    add.add_argument("--every", choices=["daily", "weekly"])
    add.add_argument("--count", type=int)
    listing = sub.add_parser("list", help="show open reminders")
    listing.add_argument("--limit", type=int, default=10)
    listing.add_argument("--color", action=argparse.BooleanOptionalAction, default=False)
    load = sub.add_parser("import", help="add the reminders of an export file")
    load.add_argument("file")
    export = sub.add_parser("export", help="write upcoming reminders to a file")
    export.add_argument("file")
    export.add_argument("--format", choices=["ics"], default="ics")
    finish = sub.add_parser("done", help="mark a reminder done")
    finish.add_argument("id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "add" and args.due is None:
        parser.error("add: --due is required")
    try:
        if args.command == "add":
            when = api.parse_when(args.due)
            reminder = api.add(args.text, when, every=args.every, count=args.count)
            print(reminder.id)
        elif args.command == "list":
            now = datetime.now(UTC)
            for due, text, ident in api.upcoming(args.limit):
                line = format_line(ident, due, text)
                print(f"{RED}{line}{RESET}" if args.color and due < now else line)
        elif args.command == "import":
            print(api.import_file(Path(args.file)))
        elif args.command == "export":
            Path(args.file).write_text(ics.calendar(api.upcoming(limit=10_000)), encoding="utf-8")
        else:
            api.done(args.id)
    except (ValueError, KeyError) as exc:
        print(f"remind: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
