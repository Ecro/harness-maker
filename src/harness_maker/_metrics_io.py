"""Shared metrics.jsonl reader — date-sharded files + legacy fallback.

ADR-103: telemetry rotates per-day to ``metrics-YYYY-MM-DD.jsonl``. Readers
glob the obs dir and walk the most recent files first, falling back to the
pre-0.7.1 single ``metrics.jsonl`` so existing dashboards keep functioning
during the transition.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_DATED_RE = re.compile(r"^metrics-(\d{4}-\d{2}-\d{2})\.jsonl$")
_LEGACY_NAME = "metrics.jsonl"


def _candidate_files(obs_dir: Path, days: int) -> list[Path]:
    """Return files to read in newest-first order, capped at ``days`` recent days.

    Date-sharded files are sorted by their ISO-date stem (lexicographic order
    matches chronological order for ``YYYY-MM-DD``). The legacy
    ``metrics.jsonl`` always trails — pre-0.7.1 entries lack date sharding,
    so they are read last and treated as the oldest data.
    """
    if not obs_dir.is_dir():
        return []
    dated: list[tuple[str, Path]] = []
    legacy: Path | None = None
    for child in obs_dir.iterdir():
        if not child.is_file():
            continue
        m = _DATED_RE.match(child.name)
        if m:
            dated.append((m.group(1), child))
        elif child.name == _LEGACY_NAME:
            legacy = child
    dated.sort(key=lambda pair: pair[0], reverse=True)
    files = [p for _, p in dated[:days]]
    if legacy is not None:
        files.append(legacy)
    return files


def iter_recent_entries(
    obs_dir: Path,
    days: int = 7,
    event: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield JSONL entries from the most recent ``days`` daily files.

    The generator walks files newest-first. Within each file, entries are
    yielded in reverse (newest line first) so callers collecting the last N
    matching entries can short-circuit cheaply. Malformed lines are silently
    skipped — observability files are best-effort, never fatal.

    When ``event`` is supplied, only entries whose ``event`` field equals it
    are yielded. Pre-0.5.4 entries lacking the ``event`` tag are treated as
    ``post_tool_use`` for backward compatibility.
    """
    for path in _candidate_files(obs_dir, days):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in reversed(text.splitlines()):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(parsed, dict):
                continue
            if event is not None:
                tag = parsed.get("event", "post_tool_use")
                if tag != event:
                    continue
            yield parsed
