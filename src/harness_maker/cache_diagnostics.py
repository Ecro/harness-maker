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

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from harness_maker.economics import TurnRecord

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


def _entry_from_turn(turn: TurnRecord) -> dict[str, Any]:
    """Bridge a TurnRecord onto the entry shape `_classify_turn` reads.

    Two traps live here. (1) The two cache-write TIERS must be summed into the single
    `cache_creation_tokens` key — dropping them reclassifies every write turn as a
    sub-threshold miss and emits the wrong remediation. (2) `_parse_timestamp` requires
    an ISO **string**; `TurnRecord.ts` is a datetime, so a naive `model_dump()` bridge
    silently disables the TTL branch.
    """
    u = turn.usage
    return {
        "timestamp": turn.ts.isoformat(),
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_read_tokens": u.cache_read_tokens,
        "cache_creation_tokens": u.cache_write_5m_tokens + u.cache_write_1h_tokens,
    }


def diagnose_cache_from_turns(
    turns: Sequence[TurnRecord],
    model: str = "sonnet",
    window_turns: int = 50,
) -> CacheDiagnosis:
    """Diagnose cache health from transcript turns — the pure core.

    `window_turns` is an explicit TURN COUNT. The retired `diagnose_cache` used one
    `window` value for two different jobs (a `days=` file selector and an entry cap),
    which made its effective window undefined.

    The threshold comes from the window-level `model`, not per turn: the caller states
    which model's cache thresholds apply, matching the retired signature.
    """
    entries: list[dict[str, Any]] = []
    for turn in turns:
        entry = _entry_from_turn(turn)
        # A turn with no token signal at all says nothing about cache health. This is
        # the same skip the old path applied — and, because the retired telemetry
        # fields were structurally zero, it is why Layer 3 was inert rather than wrong.
        if not any(
            entry[k]
            for k in (
                "input_tokens",
                "output_tokens",
                "cache_read_tokens",
                "cache_creation_tokens",
            )
        ):
            continue
        entries.append(entry)
    # Keep the most recent `window_turns`, in chronological order — TTL gap math
    # depends on the ordering.
    if window_turns > 0:
        entries = entries[-window_turns:]

    if not entries:
        return _no_data(
            "No token-bearing turns in the transcript window — if running in Cursor or "
            "Codex this is expected (neither writes Claude Code session transcripts).",
            "Use Claude Code for a few turns, then re-run. If transcripts exist but "
            "nothing prices, run `python -m harness_maker.economics doctor`.",
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


def diagnose_cache_for_project(
    project_dir: Path,
    model: str = "sonnet",
    window_turns: int = 50,
    transcript_root: Path | None = None,
) -> CacheDiagnosis:
    """Project-level adapter over the pure core (ADR-005).

    The retired `diagnose_cache(metrics_path, ...)` is NOT kept as a compat shim: once
    telemetry stops writing the token fields it would answer `no_data` unconditionally
    and forever, which is a second phantom-data path in a change whose whole purpose is
    deleting them.
    """
    from harness_maker.economics_source import load_turns

    result = load_turns(project_dir, transcript_root=transcript_root)
    return diagnose_cache_from_turns(result.turns, model=model, window_turns=window_turns)
