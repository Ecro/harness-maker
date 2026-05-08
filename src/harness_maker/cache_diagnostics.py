"""Classify cache failure modes from PostToolUse telemetry.

Each turn in metrics.jsonl is classified as one of:
- hit: cache_read_tokens > 0
- miss_first: first turn — no cache could exist yet
- miss_min_threshold: prefix below the model's cache write threshold
- miss_ttl: > 5 min gap from previous turn (default TTL expired)
- miss_invalidation: prefix changed (tools, system prompt, dynamic content)

Returns a CacheDiagnosis with score, primary failure mode, evidence, remediation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

# Per Anthropic prompt-caching docs: minimum tokens that must accumulate before
# a cache write happens. Below this, cache_creation_input_tokens silently == 0.
_THRESHOLDS: dict[str, int] = {
    "haiku": 4096,
    "opus": 1024,
    "sonnet": 1024,
}
_DEFAULT_THRESHOLD = 1024
_TTL_SECONDS = 5 * 60  # 5-minute default TTL


class CacheDiagnosis(BaseModel):
    """Aggregate diagnosis of cache hit rate over a sample window."""

    model_config = ConfigDict(strict=True, extra="forbid")

    hit_rate: int  # 0-100
    score: int  # 0-100, dimension score for ai-readiness composite
    sample_size: int
    primary_failure: str | None
    evidence: str
    remediation: str
    counters: dict[str, int]
    ttl_regression: bool = False
    ttl_regression_detail: str = ""


def _threshold_for_model(model: str) -> int:
    m = model.lower()
    for key, val in _THRESHOLDS.items():
        if key in m:
            return val
    return _DEFAULT_THRESHOLD


def _parse_timestamp(entry: dict[str, Any]) -> datetime | None:
    raw = entry.get("timestamp") or entry.get("ts")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _int_field(entry: dict[str, Any], key: str) -> int:
    val = entry.get(key, 0)
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


def _classify_turn(
    entry: dict[str, Any],
    prev_entry: dict[str, Any] | None,
    threshold: int,
) -> str:
    in_tok = _int_field(entry, "input_tokens")
    read_tok = _int_field(entry, "cache_read_tokens")
    creation_tok = _int_field(entry, "cache_creation_tokens")

    if read_tok > 0:
        return "hit"

    # No cache read = a miss. Classify the cause:

    # 1. Prefix below threshold — cache write would never have happened.
    #    Detected by: no read AND no creation AND tiny input.
    if creation_tok == 0 and (in_tok + read_tok) < threshold:
        return "miss_min_threshold"

    # 2. First turn — no prior cache could exist.
    if prev_entry is None:
        return "miss_first"

    # 3. TTL expired — gap > 5 min from previous turn.
    ts = _parse_timestamp(entry)
    prev_ts = _parse_timestamp(prev_entry)
    if ts and prev_ts and (ts - prev_ts).total_seconds() > _TTL_SECONDS:
        return "miss_ttl"

    # 4. Otherwise: prefix changed mid-session (tools, system prompt, dynamic).
    return "miss_invalidation"


def _score_from_hit_rate(hit_rate: int) -> int:
    if hit_rate >= 80:
        return 100
    if hit_rate >= 60:
        return 80
    if hit_rate >= 40:
        return 60
    if hit_rate >= 20:
        return 40
    if hit_rate >= 5:
        return 20
    return 0


def _no_data(message: str, remediation: str) -> CacheDiagnosis:
    return CacheDiagnosis(
        hit_rate=0,
        score=50,  # neutral — cannot assess
        sample_size=0,
        primary_failure="no_data",
        evidence=message,
        remediation=remediation,
        counters={},
    )


def _build_evidence(
    primary: str,
    counters: dict[str, int],
    sample_size: int,
    threshold: int,
    avg_prefix: int,
    model: str,
) -> tuple[str, str]:
    if primary == "miss_min_threshold":
        return (
            f"{counters['miss_min_threshold']} of {sample_size} turns had "
            f"prefix < {threshold} tokens (avg {avg_prefix}) — below the "
            f"{model} cache write threshold, so no cache was written.",
            f"Bulk up the static prefix: expand CLAUDE.md, register more "
            f"tools, or load skills at session start. Goal: prefix ≥ {threshold} tokens.",
        )
    if primary == "miss_ttl":
        return (
            f"{counters['miss_ttl']} of {sample_size} turns had > 5 min "
            "gap from the previous turn — the default cache TTL expired "
            "between calls and the cache had to be re-written.",
            "Either keep sessions tighter (< 5 min between turns) or enable "
            "the 1-hour extended TTL for long planning sessions.",
        )
    if primary == "miss_invalidation":
        return (
            f"{counters['miss_invalidation']} of {sample_size} turns wrote "
            "a fresh cache despite a recent prior turn — the prefix changed. "
            "Common causes: tool definitions modified, system prompt mutated, "
            "or dynamic values (date, session vars) injected into the static portion.",
            "Move dynamic values out of the static prefix into the user turn. "
            "Avoid changing tool definitions mid-session. Pin the system prompt.",
        )
    return (f"Cache miss reasons: {counters}", "See evidence.")


def _detect_ttl_regression(
    entries: list[dict[str, Any]],
    threshold: int,
) -> tuple[bool, str]:
    """Compare TTL miss rate between first and second half of the window."""
    if len(entries) < 10:
        return False, ""
    mid = len(entries) // 2
    first_half = entries[:mid]
    second_half = entries[mid:]

    def _ttl_miss_rate(segment: list[dict[str, Any]]) -> float:
        if not segment:
            return 0.0
        ttl_count = 0
        prev: dict[str, Any] | None = None
        for e in segment:
            kind = _classify_turn(e, prev, threshold)
            if kind == "miss_ttl":
                ttl_count += 1
            prev = e
        return ttl_count / len(segment)

    rate_early = _ttl_miss_rate(first_half)
    rate_recent = _ttl_miss_rate(second_half)
    if rate_recent > rate_early + 0.15 and rate_recent > 0.2:
        return True, (
            f"TTL miss rate increased from {rate_early:.0%} (early) to "
            f"{rate_recent:.0%} (recent) — possible cache TTL regression. "
            f"Check for increased inter-turn latency or session gaps."
        )
    return False, ""


def diagnose_cache(
    metrics_path: Path,
    model: str = "sonnet",
    window: int = 50,
) -> CacheDiagnosis:
    """Analyze the last `window` entries of metrics.jsonl to diagnose cache health."""
    if not metrics_path.is_file():
        return _no_data(
            "No metrics.jsonl yet — telemetry hook may not be installed or has not fired.",
            "Run /hm:make to install the PostToolUse telemetry hook, "
            "then use Claude Code for a few turns.",
        )

    try:
        lines = metrics_path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return _no_data(
            f"Could not read metrics.jsonl: {e}",
            "Check file permissions on .claude/observability/metrics.jsonl",
        )

    # Walk backwards from the tail, collecting the last `window`
    # post_tool_use entries even when the file is dominated by Cursor `stop`
    # entries (those carry no tokens — see telemetry.py docstring). Treat
    # entries lacking the `event` tag as post_tool_use for backward compat
    # with pre-0.5.4 metrics files.
    entries: list[dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(parsed, dict):
            continue
        event = parsed.get("event", "post_tool_use")
        if event != "post_tool_use":
            continue
        # 0.7.0 wiring: Cursor postToolUse entries land here too but Cursor
        # does not surface usage data, so all token fields are 0. Skip them
        # — they convey tool-call timeline (handled elsewhere) but say
        # nothing about cache health and would otherwise pollute hit-rate.
        if (
            parsed.get("input_tokens", 0) == 0
            and parsed.get("output_tokens", 0) == 0
            and parsed.get("cache_read_tokens", 0) == 0
            and parsed.get("cache_creation_tokens", 0) == 0
        ):
            continue
        entries.append(parsed)
        if len(entries) >= window:
            break
    entries.reverse()  # restore chronological order for TTL gap calculation

    if not entries:
        return _no_data(
            "metrics.jsonl exists but contains no token-bearing entries — "
            "if running in Cursor IDE, this is expected (Cursor does not "
            "surface token usage to hooks). Run from Claude Code for "
            "cache-diagnostic data.",
            "For Cursor users: cost data lives in cursor.com/settings → Usage. "
            "For Claude Code: use it for a few turns to accumulate telemetry.",
        )

    threshold = _threshold_for_model(model)
    counters = {
        "hit": 0,
        "miss_first": 0,
        "miss_min_threshold": 0,
        "miss_invalidation": 0,
        "miss_ttl": 0,
    }
    total_prefix = 0

    prev: dict[str, Any] | None = None
    for entry in entries:
        kind = _classify_turn(entry, prev, threshold)
        counters[kind] = counters.get(kind, 0) + 1
        total_prefix += (
            _int_field(entry, "input_tokens")
            + _int_field(entry, "cache_read_tokens")
            + _int_field(entry, "cache_creation_tokens")
        )
        prev = entry

    sample_size = len(entries)
    hit_rate = round(100 * counters["hit"] / sample_size) if sample_size else 0
    avg_prefix = total_prefix // sample_size if sample_size else 0
    score = _score_from_hit_rate(hit_rate)

    # Pick the most-common actionable miss as primary (skip miss_first — expected).
    actionable = {
        k: v for k, v in counters.items() if k.startswith("miss_") and k != "miss_first" and v > 0
    }
    if not actionable or hit_rate >= 80:
        return CacheDiagnosis(
            hit_rate=hit_rate,
            score=score,
            sample_size=sample_size,
            primary_failure=None,
            evidence=f"Cache healthy: {hit_rate}% hit rate over {sample_size} turns.",
            remediation="No action needed.",
            counters=counters,
        )

    primary = max(actionable, key=lambda k: actionable[k])
    evidence, remediation = _build_evidence(
        primary, counters, sample_size, threshold, avg_prefix, model
    )
    ttl_reg, ttl_detail = _detect_ttl_regression(entries, threshold)
    return CacheDiagnosis(
        hit_rate=hit_rate,
        score=score,
        sample_size=sample_size,
        primary_failure=primary,
        evidence=evidence,
        remediation=remediation,
        counters=counters,
        ttl_regression=ttl_reg,
        ttl_regression_detail=ttl_detail,
    )
