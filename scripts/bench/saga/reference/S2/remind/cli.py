"""Command line: `python -m remind.cli add|list|done ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from remind import api
from remind.fmt import format_line


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="remind")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="add a reminder")
    add.add_argument("text")
    add.add_argument("--when", required=True, help="due time, 'YYYY-MM-DD HH:MM' (UTC)")
    add.add_argument("--every", choices=["daily", "weekly"])
    add.add_argument("--count", type=int)
    listing = sub.add_parser("list", help="show open reminders")
    listing.add_argument("--limit", type=int, default=10)
    load = sub.add_parser("import", help="add the reminders of an export file")
    load.add_argument("file")
    finish = sub.add_parser("done", help="mark a reminder done")
    finish.add_argument("id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "add":
            when = api.parse_when(args.when)
            reminder = api.add(args.text, when, every=args.every, count=args.count)
            print(reminder.id)
        elif args.command == "list":
            for due, text, ident in api.upcoming(args.limit):
                print(format_line(ident, due, text))
        elif args.command == "import":
            print(api.import_file(Path(args.file)))
        else:
            api.done(args.id)
    except (ValueError, KeyError) as exc:
        print(f"remind: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
