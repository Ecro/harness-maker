"""Classify cache failure modes from PostToolUse telemetry.

Each turn in metrics.jsonl is classified as one of:
- hit: cache_read_tokens > 0
- miss_first: first turn — no cache could exist yet
- miss_min_threshold: prefix below the model's published cache write minimum
- miss_unknown_model: the model publishes no minimum, so that test cannot run
- miss_ttl: gap exceeded the TTL tier that applied to the turn (ADR-005)
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
#
# The published minimums are NON-MONOTONIC inside one family — Opus 5 is 512 while
# Opus 4.6 is 4096, eight times larger. A family-prefix table therefore cannot express
# them at all, and the one that shipped here answered 1024 for every Opus. Keys are
# matched as substrings, LONGEST-MATCH wins (the same contract as
# `economics.resolve_model_family`); a first-match scan lets `"opus"` shadow `"opus-5"`.
#
# There are deliberately NO bare-family keys. An id that matches nothing resolves to
# `None`, and the classifier reports `miss_unknown_model` rather than measuring the
# prefix against a guess — the absent case must be visible, not silently defaulted.
#
# `sonnet-4-6` and `sonnet-5` are enumerated at the published Sonnet minimum of 1024;
# they are here because they are models users actually run. (An earlier comment
# justified `sonnet-4-6` as "the hard-coded default of every `ai_readiness` caller,
# without which /hm:health's default window would degrade wholesale". That stopped
# being true in this same change: `model=` is now only a per-turn FALLBACK, and
# `economics_source` stamps each turn with its own id, so the caller default applies
# only to model-less turns.)
#
# KNOWN LIMITATION — keys are matched as SUBSTRINGS, so a longer id that contains a
# shorter key inherits it: `claude-opus-5-1` would contain `opus-5` and silently take
# 512. That is a guess of exactly the kind this table refuses to record deliberately.
# It is not fixed here because `economics.resolve_model_family` uses the same matching
# contract and ADR-002 locks it unchanged; a date-suffixed id like
# `claude-haiku-4-5-20251001` is real and depends on substring matching working. Making
# only this matcher stricter would split a contract the code states is shared.
_MIN_CACHEABLE_PREFIX: dict[str, int] = {
    "opus-5": 512,
    "opus-4-8": 1024,
    "opus-4-7": 2048,
    "opus-4-6": 4096,
    # NOTE on the ids that are absent. `PRICE_TABLE` prices `opus-4-5` and
    # `sonnet-4-5`; this table does not carry them, and that asymmetry is deliberate.
    # An intermediate revision added both at 1024 to make the two tables agree — but
    # there is no release-specific published minimum for either id, so 1024 was an
    # inherited guess, and recording a guess here is exactly what returning `None` for
    # an unknown model exists to prevent. A wrong RATE yields an approximate dollar
    # figure; a wrong MINIMUM yields a confident `miss_min_threshold` verdict and a
    # remediation telling the user to grow a prefix that may already be large enough.
    # Pricing and diagnosing have different tolerances for a guess, so the two tables
    # are allowed to disagree about which models they can speak to.
    "sonnet-4-6": 1024,
    "sonnet-5": 1024,
    "haiku-4-5": 4096,
}

_TTL_5M_SECONDS = 5 * 60
_TTL_1H_SECONDS = 60 * 60


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


def _threshold_for_model(model: str | None) -> int | None:
    """Minimum cacheable prefix for `model`, or None when it is not published.

    Returns None rather than a default so an unknown model cannot be measured
    against a guessed threshold — the sub-threshold verdict is undefined without a
    known minimum, and inventing one produces a confident, fabricated diagnosis.
    """
    if not model:
        return None
    m = model.lower()
    matches = [key for key in _MIN_CACHEABLE_PREFIX if key in m]
    if not matches:
        return None
    return _MIN_CACHEABLE_PREFIX[max(sorted(matches), key=len)]


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


def _ttl_tiers(entries: Sequence[dict[str, Any]]) -> list[tuple[int, bool]]:
    """Applicable TTL per entry, and whether the tier was observed or assumed.

    ADR-005: the tier for the gap ending at entry `i` comes from the most recent prior
    turn **in the same session** that wrote cache tokens — 1h tokens present wins, else
    5m. With no attributable prior write the 5m default applies and the flag records
    that it was assumed rather than observed.

    Computed in ONE forward pass over the full history, not by scanning backward from
    each entry. The backward form was O(window x history) once the window stopped being
    a slice, and O(N^2) in the uncapped `window_turns <= 0` mode over transcripts that
    have no turn-count bound. Carrying "the most recent write tier seen so far, per
    session" forward is exactly equivalent — the backward scan returned the first
    writing predecessor in the session, which is the last one this loop recorded.

    ADR-012 boundary rule 1: the result is indexed by ABSOLUTE position over the full
    history, so a caller re-classifying a half-window (`_detect_ttl_regression`) or a
    trailing reporting window still sees writes that happened earlier. Confining the
    lookup to a segment would strip those turns of an attributable write, fall back to
    the 5m default, and manufacture a regression along the very axis that helper
    measures.

    ADR-012 boundary rule 2: only the TIER lookup is session-scoped. The gap arithmetic
    still runs against the chronologically previous entry, whatever session it is from.
    """
    tiers: list[tuple[int, bool]] = []
    # `economics_source` emits `str(data.get("sessionId") or "")`, so a transcript line
    # with no sessionId collapses to `""` — and every such turn would then compare EQUAL
    # to every other, inheriting a TTL tier across unrelated sessions. An unidentifiable
    # session has no attributable prior write by definition: it is never recorded here
    # and never reads from here, so it fails closed to the 5m default rather than open
    # to a borrowed 1h tier.
    latest_write: dict[str, tuple[int, bool]] = {}
    for entry in entries:
        session = entry.get("session_id")
        key = str(session) if session else ""
        tiers.append(
            latest_write.get(key, (_TTL_5M_SECONDS, False)) if key else (_TTL_5M_SECONDS, False)
        )
        if not key:
            continue
        if _int_field(entry, "cache_write_1h_tokens") > 0:
            latest_write[key] = (_TTL_1H_SECONDS, True)
        elif _int_field(entry, "cache_write_5m_tokens") > 0:
            latest_write[key] = (_TTL_5M_SECONDS, True)
    return tiers


def _classify_turn(
    entry: dict[str, Any],
    prev_entry: dict[str, Any] | None,
    threshold: int | None,
    ttl_seconds: int = _TTL_5M_SECONDS,
) -> str:
    in_tok = _int_field(entry, "input_tokens")
    read_tok = _int_field(entry, "cache_read_tokens")
    creation_tok = _int_field(entry, "cache_creation_tokens")

    if read_tok > 0:
        return "hit"

    # No cache read = a miss. Classify the cause:

    # 1. Prefix below threshold — cache write would never have happened.
    #    Detected by: no read AND no creation AND tiny input.
    #    A `None` threshold means the model publishes no minimum, so this ONE test
    #    cannot run. Skip it and keep going: an unknown minimum says nothing about
    #    whether the turn was the session's first, whether the TTL expired, or whether
    #    the prefix changed. An earlier draft returned `miss_unknown_model` here, ahead
    #    of all three — which silently disabled them and, because
    #    `_detect_ttl_regression` only counts `miss_ttl`, made TTL regression
    #    undetectable for the entire window.
    if creation_tok == 0 and threshold is not None and (in_tok + read_tok) < threshold:
        return "miss_min_threshold"

    # 2. First turn — no prior cache could exist.
    if prev_entry is None:
        return "miss_first"

    # 3. TTL expired — gap exceeded the tier that actually applied (ADR-005).
    ts = _parse_timestamp(entry)
    prev_ts = _parse_timestamp(prev_entry)
    if ts and prev_ts and (ts - prev_ts).total_seconds() > ttl_seconds:
        return "miss_ttl"

    # 4. `miss_invalidation` is a conclusion BY ELIMINATION — "not sub-threshold, not
    #    first, not expired, therefore the prefix changed". With no published minimum
    #    the first of those is unproven, so the elimination does not close. Report the
    #    gap instead of guessing.
    if creation_tok == 0 and threshold is None:
        return "miss_unknown_model"

    # 5. Otherwise: prefix changed mid-session (tools, system prompt, dynamic).
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


def _tier_label(seconds: int) -> str:
    return "1 hour" if seconds >= _TTL_1H_SECONDS else "5 min"


_MODEL_LIST_CAP = 5
_MODEL_ID_CAP = 64


def _render_model_list(models: set[str]) -> str:
    """Format transcript-derived model ids for prose the user reads.

    These ids come out of session `.jsonl` files. `economics_source._clip` already
    strips non-printables and caps each at 64 chars, so this is defence in depth rather
    than the only barrier — but `_build_evidence`'s output reaches an `ImprovementPlan`
    detail field, and an unbounded `", ".join` over a whole window's worth of distinct
    ids would be a presentation problem even with entirely well-formed input.
    """
    if not models:
        return "no model id recorded on those turns"
    ordered = sorted(models)
    shown = [m.replace("`", "'")[:_MODEL_ID_CAP] for m in ordered[:_MODEL_LIST_CAP]]
    listed = ", ".join(shown)
    remainder = len(ordered) - len(shown)
    return f"{listed} (+{remainder} more)" if remainder > 0 else listed


def _build_evidence(
    primary: str,
    counters: dict[str, int],
    sample_size: int,
    avg_prefix: int,
    thresholds_applied: set[int],
    unknown_models: set[str],
    ttl_miss_tiers: list[int],
    assumed_tier_turns: int,
) -> tuple[str, str]:
    """Render user-facing evidence for the dominant failure mode.

    ADR-012 boundary rule 3: nothing here may hard-code the 5-minute framing or format
    a threshold that may be `None`. With per-turn resolution a window can carry several
    thresholds and several TTL tiers at once, so the text reports what actually applied
    rather than a single window-level number.
    """
    if primary == "miss_unknown_model":
        # Deliberately NOT actionable prose. An earlier revision told the user to
        # "upgrade harness-maker … report the id above so it can be added", which
        # contradicted this module's own policy 250 lines up: `opus-4-5` / `sonnet-4-5`
        # were REMOVED from the table precisely because no release-specific minimum is
        # published for them, and they will not be re-added. Every user of a
        # currently-shipping model in that set was being handed an errand that the code
        # refuses to complete. State the limitation; do not manufacture a remedy.
        return (
            f"{counters['miss_unknown_model']} of {sample_size} turns ran on a model "
            f"with no published minimum cacheable prefix on record "
            f"({_render_model_list(unknown_models)}) — the sub-threshold test could not "
            "run for them, so their misses are recorded as unexplained rather than "
            "attributed to a cause.",
            "No action is available on your side: whether a minimum exists to record is "
            "a property of the model's published documentation, not of this project. "
            "The other failure modes in this window are still measured normally.",
        )
    if primary == "miss_min_threshold":
        if len(thresholds_applied) == 1:
            goal = f"prefix ≥ {next(iter(thresholds_applied))} tokens"
            band = f"the applicable {next(iter(thresholds_applied))}-token minimum"
        else:
            lo, hi = min(thresholds_applied), max(thresholds_applied)
            goal = f"prefix ≥ {hi} tokens (the largest minimum in this window)"
            band = f"their models' minimums ({lo}–{hi} tokens — these differ per model)"
        return (
            f"{counters['miss_min_threshold']} of {sample_size} turns had a prefix "
            f"below {band} (avg {avg_prefix} tokens), so no cache was written.",
            "Bulk up the static prefix: expand CLAUDE.md, register more tools, or "
            f"load skills at session start. Goal: {goal}.",
        )
    if primary == "miss_ttl":
        tiers = sorted({_tier_label(t) for t in ttl_miss_tiers}) or [_tier_label(_TTL_5M_SECONDS)]
        tier_text = " and ".join(tiers)
        assumed = (
            f" The tier was assumed for {assumed_tier_turns} turn(s) with no "
            "attributable prior cache write in their session."
            if assumed_tier_turns
            else ""
        )
        remedy = (
            "Keep turns closer together than the tier that applied"
            if "1 hour" in tiers
            else "Either keep sessions tighter than the 5 min default tier or enable "
            "the 1-hour extended TTL for long planning sessions"
        )
        return (
            f"{counters['miss_ttl']} of {sample_size} turns exceeded the "
            f"{tier_text} cache TTL that applied to them, so the cache had to be "
            f"re-written.{assumed}",
            f"{remedy}.",
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
    fallback_model: str | None,
    window_start: int = 0,
    tiers: list[tuple[int, bool]] | None = None,
) -> tuple[bool, str]:
    """Compare TTL miss rate between first and second half of the reporting window.

    `entries` is the FULL history; `window_start` is where the reporting window opens.
    Both the TTL tier lookup AND the gap arithmetic run against the full list by
    absolute index — ADR-012 boundary rule 1, and the same reason the caller passes a
    start index instead of a slice. Confining either to a segment leaves later turns
    without an attributable prior write or predecessor, falls back to the 5m default,
    and turns a healthy 1h-tier session into a fabricated regression.

    `prev` is therefore seeded from `entries[start - 1]` for each half, matching the
    main classification loop. An earlier revision seeded the main loop but not this
    one, so the two paths classified the same turn differently and the early half's
    rate was under-counted by `1 / (n // 2)` — which for a short window exceeds the
    0.15 trigger below.

    `tiers` is the caller's precomputed `_ttl_tiers(entries)`; recomputing it here
    would walk the whole history a second time for a field with no consumer.
    """
    n = len(entries) - window_start
    if n < 10:
        return False, ""
    mid = window_start + n // 2
    if tiers is None:
        tiers = _ttl_tiers(entries)

    def _ttl_miss_rate(start: int, stop: int) -> float:
        if stop <= start:
            return 0.0
        ttl_count = 0
        prev: dict[str, Any] | None = entries[start - 1] if start else None
        for i in range(start, stop):
            e = entries[i]
            threshold = _threshold_for_model(e.get("model") or fallback_model)
            if _classify_turn(e, prev, threshold, tiers[i][0]) == "miss_ttl":
                ttl_count += 1
            prev = e
        return ttl_count / (stop - start)

    rate_early = _ttl_miss_rate(window_start, mid)
    rate_recent = _ttl_miss_rate(mid, len(entries))
    if rate_recent > rate_early + 0.15 and rate_recent > 0.2:
        return True, (
            f"TTL miss rate increased from {rate_early:.0%} (early) to "
            f"{rate_recent:.0%} (recent) — possible cache TTL regression. "
            f"Check for increased inter-turn latency or session gaps."
        )
    return False, ""


def _entry_from_turn(turn: TurnRecord) -> dict[str, Any]:
    """Bridge a TurnRecord onto the entry shape `_classify_turn` reads.

    Three traps live here. (1) The two cache-write TIERS must ALSO be summed into the
    single `cache_creation_tokens` key — dropping that key reclassifies every write turn
    as a sub-threshold miss and emits the wrong remediation. The per-tier keys are
    carried IN ADDITION, never instead. (2) `_parse_timestamp` requires an ISO
    **string**; `TurnRecord.ts` is a datetime, so a naive `model_dump()` bridge silently
    disables the TTL branch. (3) `model` and `session_id` are load-bearing, not
    decoration: without `model` the per-model minimums resolve correctly and are then
    never applied to anything (the corrected table would be dead code from /hm:health's
    point of view), and without `session_id` the TTL tier leaks across sessions, which
    `diagnose_cache_from_turns` invites by flattening every session into one list.
    """
    u = turn.usage
    return {
        "timestamp": turn.ts.isoformat(),
        "model": turn.model,
        "session_id": turn.session_id,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_read_tokens": u.cache_read_tokens,
        "cache_write_5m_tokens": u.cache_write_5m_tokens,
        "cache_write_1h_tokens": u.cache_write_1h_tokens,
        "cache_creation_tokens": u.cache_write_5m_tokens + u.cache_write_1h_tokens,
    }


def diagnose_cache_from_turns(
    turns: Sequence[TurnRecord],
    model: str | None = None,
    window_turns: int = 50,
) -> CacheDiagnosis:
    """Diagnose cache health from transcript turns — the pure core.

    `window_turns` is an explicit TURN COUNT. The retired `diagnose_cache` used one
    `window` value for two different jobs (a `days=` file selector and an entry cap),
    which made its effective window undefined.

    `model` is a per-turn FALLBACK for turns whose own `model` is absent — not the
    window-level answer it used to be. The published minimum cacheable prefix is
    non-monotonic within a family (Opus 5 = 512, Opus 4.6 = 4096), so one threshold
    per window cannot be right for a mixed window; and every production caller passed
    a hard-coded string, which meant the table was never exercised by real data.
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
    # The REPORTING window is the most recent `window_turns`, in chronological order —
    # TTL gap math depends on the ordering. It is expressed as a start INDEX, not a
    # slice: `_ttl_for_entry` must be able to see a cache write that happened just
    # before the window opened. An earlier draft truncated the list here, so a 1h write
    # at turn 50 was invisible to a window starting at turn 51 — the tier silently fell
    # back to 5m and manufactured `miss_ttl` verdicts for turns that were inside their
    # actual TTL. Same failure as ADR-012's segment-boundary rule, at a boundary that
    # rule did not name.
    window_start = max(0, len(entries) - window_turns) if window_turns > 0 else 0
    window = entries[window_start:]

    if not window:
        return _no_data(
            "No token-bearing turns in the transcript window — if running in Cursor or "
            "Codex this is expected (neither writes Claude Code session transcripts).",
            "Use Claude Code for a few turns, then re-run. If transcripts exist but "
            "nothing prices, run `python -m harness_maker.economics doctor`.",
        )

    counters = {
        "hit": 0,
        "miss_first": 0,
        "miss_min_threshold": 0,
        "miss_invalidation": 0,
        "miss_ttl": 0,
        "miss_unknown_model": 0,
    }
    # Every accumulator below is keyed on the turn's CLASSIFICATION, not on the turn.
    # An earlier draft added each turn's threshold to `thresholds_applied` and each
    # unknown id to `unknown_models` before classifying, so a window of haiku HITS
    # (4096) plus a few sub-threshold opus-5 misses (512) told the user to grow the
    # prefix to 4096 — a number computed entirely from turns that did not fail. That is
    # the same "report a threshold that did not apply" defect this change exists to
    # remove, surviving one layer up. `avg_prefix` is likewise the average over the
    # offending turns only; averaging in large hit prefixes inflated it.
    offending_prefix_total = 0
    thresholds_applied: set[int] = set()
    unknown_models: set[str] = set()
    ttl_miss_tiers: list[int] = []
    assumed_tier_turns = 0

    tiers = _ttl_tiers(entries)
    # The gap arithmetic must cross the window boundary too, not only the tier lookup:
    # `entries[window_start - 1]` is in hand, so reporting the window's first turn as
    # the session's first would be false whenever a predecessor exists.
    prev: dict[str, Any] | None = entries[window_start - 1] if window_start else None
    for i, entry in enumerate(entries[window_start:], start=window_start):
        entry_model = entry.get("model") or model
        threshold = _threshold_for_model(entry_model)
        ttl_seconds, tier_observed = tiers[i]
        kind = _classify_turn(entry, prev, threshold, ttl_seconds)
        counters[kind] = counters.get(kind, 0) + 1
        if kind == "miss_unknown_model":
            unknown_models.add(str(entry_model) if entry_model else "(no model on turn)")
        if kind == "miss_min_threshold" and threshold is not None:
            thresholds_applied.add(threshold)
            offending_prefix_total += _int_field(entry, "input_tokens") + _int_field(
                entry, "cache_read_tokens"
            )
        elif kind == "miss_ttl":
            ttl_miss_tiers.append(ttl_seconds)
            if not tier_observed:
                assumed_tier_turns += 1
        prev = entry

    sample_size = len(window)
    hit_rate = round(100 * counters["hit"] / sample_size) if sample_size else 0
    n_sub = counters["miss_min_threshold"]
    avg_prefix = offending_prefix_total // n_sub if n_sub else 0
    score = _score_from_hit_rate(hit_rate)

    # Pick the most-common actionable miss as primary (skip miss_first — expected).
    actionable = {
        k: v for k, v in counters.items() if k.startswith("miss_") and k != "miss_first" and v > 0
    }
    # The healthy shortcut must not fire while the diagnosis is INCOMPLETE. A window
    # with unknown-minimum turns has an unmeasured dimension, so "No action needed" is
    # a claim the data does not support — and above 80% hit rate that degradation was
    # exactly where it became invisible, which defeats the reason the unknown case is
    # reported at all.
    #
    # Two separate conditions, deliberately NOT merged. `not actionable` means there is
    # no primary to report at all — `max()` over it would raise, and an earlier revision
    # that folded the unknown-minimum guard into this one clause crashed on exactly that
    # window. `hit_rate >= 80` is the separate "good enough to stop looking" cutoff, and
    # only THAT one is suppressed when unknown-minimum turns are present: above 80% is
    # where an incomplete diagnosis would otherwise become invisible. The guard reads
    # the CLASSIFICATION, not a parallel per-turn property — an earlier revision tracked
    # the property instead, which made the shortcut unreachable forever for anyone
    # running a model whose minimum this table will never carry.
    if not actionable or (hit_rate >= 80 and counters["miss_unknown_model"] == 0):
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
        primary,
        counters,
        sample_size,
        avg_prefix,
        thresholds_applied,
        unknown_models,
        ttl_miss_tiers,
        assumed_tier_turns,
    )
    ttl_reg, ttl_detail = _detect_ttl_regression(entries, model, window_start, tiers)
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
    model: str | None = None,
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
