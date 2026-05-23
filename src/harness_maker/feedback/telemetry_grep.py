"""Bounded local telemetry grep for the feedback dispatcher block.

PLAN-auto-feedback-2026-05 ADR-005: in-band LLM judgment reads ≤2KB of context
via these helpers, then decides whether a harness-self issue occurred and
whether to write a draft. No socket calls — uses ``_metrics_io`` for
rotation-aware reads (wiki:convention metrics-rotation-reader-via-_metrics_io).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_maker._metrics_io import _candidate_files, iter_recent_entries

TELEMETRY_GREP_MAX_BYTES = 2048
_TRUNC_MARKER = "...<truncated>"


def _bounded_dumps(payload: object) -> str:
    """JSON-serialize and cap at TELEMETRY_GREP_MAX_BYTES."""
    out = json.dumps(payload, default=str, separators=(",", ":"))
    if len(out) > TELEMETRY_GREP_MAX_BYTES:
        out = out[: TELEMETRY_GREP_MAX_BYTES - len(_TRUNC_MARKER)] + _TRUNC_MARKER
    return out


def last_stop_with_trace(metrics_dir: Path) -> str:
    """Return JSON of the last ``stop`` event + matching ``post_tool_use`` rows.

    Walks today's ``metrics-YYYY-MM-DD.jsonl`` (and one fallback day) newest-first
    via ``_metrics_io.iter_recent_entries``. Returns the empty string when no
    stop event exists (clean session). The returned string is capped at
    ``TELEMETRY_GREP_MAX_BYTES`` bytes — callers feeding this into an LLM
    context window can rely on that bound.
    """
    if not metrics_dir.is_dir():
        return ""
    stop_event: dict[str, Any] | None = None
    for entry in iter_recent_entries(metrics_dir, days=1, event="stop"):
        stop_event = entry
        break
    if stop_event is None:
        return ""
    trace_id = stop_event.get("trace_id")
    tool_rows: list[dict[str, Any]] = []
    if isinstance(trace_id, str) and trace_id:
        for entry in iter_recent_entries(metrics_dir, days=1, event="post_tool_use"):
            if entry.get("trace_id") == trace_id:
                tool_rows.append(entry)
                # Stop padding once we'd exceed the budget. Keep most-recent first.
                if len(tool_rows) >= 20:
                    break
    payload = {"stop": stop_event, "tool_uses": tool_rows}
    return _bounded_dumps(payload)


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    """Return up to ``limit`` newest entries (best-effort; malformed lines skipped)."""
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in reversed(text.splitlines()):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
            if len(out) >= limit:
                break
    return out


def gather_recent_signals(obs_dir: Path) -> str:
    """Return a bounded JSON bundle of the 3 PLAN-listed harness-self signals.

    (a) last stop event + trace tool uses from ``metrics-{today}.jsonl``,
    (d) recent ``silent-intent-miss-*.jsonl`` rows (any slug, newest 5),
    (e) recent ``review-{today}.jsonl`` rows where ``build_break_count > 0``
        or ``auto_fix_reverted_n > 0`` (newest 5).

    All three live under ``obs_dir`` (= ``.claude/observability``). The combined
    output is capped at ``TELEMETRY_GREP_MAX_BYTES``. Truncation marker appears
    at the end so the LLM consumer can detect partial data.
    """
    bundle: dict[str, Any] = {
        "metrics": last_stop_with_trace(obs_dir),
        "silent_intent_miss": [],
        "build_break": [],
    }
    if obs_dir.is_dir():
        # silent-intent-miss-{slug}.jsonl (one per task slug)
        sim_rows: list[dict[str, Any]] = []
        for child in obs_dir.iterdir():
            if (
                child.is_file()
                and child.name.startswith("silent-intent-miss-")
                and child.suffix == ".jsonl"
            ):
                sim_rows.extend(_read_jsonl_tail(child, limit=5))
        bundle["silent_intent_miss"] = sim_rows[:5]

        # review-{date}.jsonl — filter to harness-self failure modes only.
        review_files = [
            p for p in _candidate_files(obs_dir, days=1) if p.name.startswith("review-")
        ]
        # _candidate_files filters metrics-*.jsonl; review files need a separate scan.
        for child in obs_dir.iterdir():
            if (
                child.is_file()
                and child.name.startswith("review-")
                and child.suffix == ".jsonl"
                and child not in review_files
            ):
                review_files.append(child)
        bb_rows: list[dict[str, Any]] = []
        for rf in review_files:
            for row in _read_jsonl_tail(rf, limit=10):
                bbc = row.get("build_break_count", 0)
                rev = row.get("auto_fix_reverted_n", 0)
                if (isinstance(bbc, int) and bbc > 0) or (isinstance(rev, int) and rev > 0):
                    bb_rows.append(row)
                    if len(bb_rows) >= 5:
                        break
            if len(bb_rows) >= 5:
                break
        bundle["build_break"] = bb_rows
    return _bounded_dumps(bundle)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m harness_maker.feedback.telemetry_grep --metrics-dir <p>``.

    Prints the bounded telemetry bundle to stdout for the dispatcher Bash hook.
    No flags besides ``--metrics-dir``; future expansion lives in
    ``draft_writer.main()``.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="harness_maker.feedback.telemetry_grep")
    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=Path(".claude/observability"),
        help="Observability dir (default: .claude/observability).",
    )
    args = parser.parse_args(argv)
    out = gather_recent_signals(args.metrics_dir)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
