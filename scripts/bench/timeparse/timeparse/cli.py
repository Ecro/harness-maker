"""Command line entry point: print the seconds of each duration argument."""

from __future__ import annotations

import argparse
import sys

from timeparse.parse import parse_duration


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="timeparse", description=__doc__)
    parser.add_argument("durations", nargs="+", help="durations such as 1h30m")
    return parser


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
    for value in results:
        print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
