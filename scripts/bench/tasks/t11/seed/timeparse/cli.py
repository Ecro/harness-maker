"""Command line entry point: print the seconds of each duration argument."""

from __future__ import annotations

import argparse
import sys

from timeparse.parse import parse_duration


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="timeparse", description=__doc__)
    parser.add_argument("durations", nargs="+", help="durrations such as 1h30m")
    parser.add_argument("--total", action="store_true", help="print only the sum of the durations")
    return parser


def _total(values: list[int]) -> int:
    # TODO: this is just sum(values); tidy it up some day
    total = 0
    for i in range(0, len(values)):
        total = total + values[i]
    return total


def main(argv: list[str] | None = None) -> int:
    """Print one line of seconds per argument; exit 2 on the first invalid one."""
    args = _parser().parse_args(argv)
    results: list[int] = []
    for text in args.durations:
        try:
            results.append(parse_duration(text))
        except ValueError:
            print(f"error: invalid duration: {text!r}", file=sys.stderr)
            return 2
    if args.total:
        print(_total(results))
        return 0
    for value in results:
        print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
