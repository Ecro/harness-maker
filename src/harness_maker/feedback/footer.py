"""One-line locale-aware footer for the feedback dispatcher.

PLAN-auto-feedback-2026-05 ADR-005. Returns the empty string when no draft
was written this turn (silent-when-empty); otherwise returns a single line
with the exact ``gh issue create --web --body-file <path>`` command for
manual submission.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Literal

Locale = Literal["en", "ko"]

_FOOTER_TEMPLATES: dict[Locale, str] = {
    "en": "📝 feedback draft saved → {path} (run: gh issue create --web --body-file {path})",
    "ko": "📝 feedback draft 저장됨 → {path} (실행: gh issue create --web --body-file {path})",
}


def render(draft_path: Path | None, locale: str = "en") -> str:
    """Return the locale-aware footer line, or '' if draft_path is None.

    Unknown locales silently fall back to English (mirrors the project-wide
    locale policy in ``i18n.t``).
    """
    if draft_path is None:
        return ""
    locale_key: Locale = "ko" if locale == "ko" else "en"
    return _FOOTER_TEMPLATES[locale_key].format(path=draft_path)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m harness_maker.feedback.footer --path <p> [--locale ko]``.

    Prints the footer line to stdout. Empty --path → no output (silent).
    """
    parser = argparse.ArgumentParser(prog="harness_maker.feedback.footer")
    parser.add_argument("--path", type=str, default="", help="Draft path; empty → silent.")
    parser.add_argument(
        "--locale",
        type=str,
        default="en",
        help="en | ko (default en; unknown falls back to en).",
    )
    args = parser.parse_args(argv)
    path = Path(args.path) if args.path else None
    line = render(path, locale=args.locale)
    if line:
        sys.stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
