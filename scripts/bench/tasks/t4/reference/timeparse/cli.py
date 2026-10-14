"""Command line entry point: print the seconds of each duration argument."""

from __future__ import annotations

import argparse
import sys

from timeparse.parse import parse_duration


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="timeparse", description=__doc__)
    parser.add_argument("durations", nargs="+", help="durations such as 1h30m, or - for stdin")
    parser.add_argument("--sum", action="store_true", help="print only the total")
    return parser


def _inputs(args: list[str]) -> list[str]:
    texts: list[str] = []
    for arg in args:
        if arg == "-":
            texts.extend(line.strip() for line in sys.stdin if line.strip())
        else:
            texts.append(arg.strip())
    return texts


def main(argv: list[str] | None = None) -> int:
    """Print seconds per input (or their sum); report every invalid input and exit 2."""
    args = _parser().parse_args(argv)
    results: list[int] = []
    bad = False
    for text in _inputs(args.durations):
        try:
            results.append(parse_duration(text))
        except ValueError:
            print(f"error: invalid duration: {text!r}", file=sys.stderr)
            bad = True
    if bad:
        return 2
    if args.sum:
        print(sum(results))
    else:
        for value in results:
            print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
