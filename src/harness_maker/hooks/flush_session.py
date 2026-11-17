"""Retired PreCompact/Stop hook, kept as an exit-0 stub (SPEC-opus55-stale-cuts).

Why it stays: a `settings.json` or `.codex/hooks.json` that was never re-rendered still runs
`python -m harness_maker.hooks.flush_session`, and a missing module would print an error on
every compaction. Why it does nothing: it snapshotted `.claude-progress.json`, which nothing
has written since autoloop was retired, and `/hm:execute` resumes from the SPEC, the PLAN and
the REVIEW file.
"""

from __future__ import annotations

import contextlib
import sys


def main() -> int:
    """Drain the hook payload so the host never sees a broken pipe, then succeed."""
    with contextlib.suppress(Exception):  # closed stdin is `None`; a hook must never fail here
        sys.stdin.read()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
