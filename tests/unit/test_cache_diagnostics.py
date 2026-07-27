"""Cache diagnostics — failure-mode classification and scoring."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from harness_maker.cache_diagnostics import (
    _classify_turn,
    _score_from_hit_rate,
    _threshold_for_model,
)


def _ts(offset_seconds: int = 0) -> str:
    return (
        datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC) + timedelta(seconds=offset_seconds)
    ).isoformat()


# ── _threshold_for_model ────────────────────────────────────────────────────


def test_threshold_haiku_is_4096() -> None:
    assert _threshold_for_model("claude-haiku-4-5") == 4096


def test_threshold_sonnet_is_1024() -> None:
    assert _threshold_for_model("claude-sonnet-4-6") == 1024


def test_threshold_opus_4_7_is_2048() -> None:
    """Retired the `== 1024` assertion: it encoded the family-prefix defect.

    `_THRESHOLDS` answered 1024 for every Opus because `"opus"` matched first. The
    published Opus 4.7 minimum is 2048, and this test asserted the bug (PLAN ADR-004).
    """
    assert _threshold_for_model("claude-opus-4-7") == 2048


def test_threshold_unknown_returns_none_not_a_guess() -> None:
    """Retired the `falls_back_to_1024` assertion (PLAN ADR-004).

    The 1024 default is what let an unknown model produce a confident
    `miss_min_threshold` verdict measured against a number nobody published.
    """
    assert _threshold_for_model("gpt-4") is None
    assert _threshold_for_model(None) is None


# ── _score_from_hit_rate ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("hit_rate", "expected"),
    [
        (100, 100),
        (80, 100),
        (79, 80),
        (60, 80),
        (59, 60),
        (40, 60),
        (39, 40),
        (20, 40),
        (19, 20),
        (5, 20),
        (4, 0),
        (0, 0),
    ],
)
def test_score_buckets(hit_rate: int, expected: int) -> None:
    assert _score_from_hit_rate(hit_rate) == expected


# ── _classify_turn ──────────────────────────────────────────────────────────


def test_classify_hit_when_cache_read_positive() -> None:
    entry = {"input_tokens": 100, "cache_read_tokens": 5000, "cache_creation_tokens": 0}
    assert _classify_turn(entry, prev_entry=None, threshold=1024) == "hit"


def test_classify_min_threshold_when_no_read_no_creation_tiny_input() -> None:
    entry = {"input_tokens": 500, "cache_read_tokens": 0, "cache_creation_tokens": 0}
    assert _classify_turn(entry, prev_entry=None, threshold=1024) == "miss_min_threshold"


def test_classify_first_when_creation_positive_no_prev() -> None:
    entry = {"input_tokens": 200, "cache_read_tokens": 0, "cache_creation_tokens": 5000}
    assert _classify_turn(entry, prev_entry=None, threshold=1024) == "miss_first"


def test_classify_ttl_when_gap_over_5min() -> None:
    prev = {"timestamp": _ts(0), "input_tokens": 100, "cache_read_tokens": 5000}
    entry = {
        "timestamp": _ts(400),
        "input_tokens": 100,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 5000,
    }
    assert _classify_turn(entry, prev_entry=prev, threshold=1024) == "miss_ttl"


def test_classify_invalidation_when_short_gap_and_creation_positive() -> None:
    prev = {"timestamp": _ts(0), "input_tokens": 100, "cache_read_tokens": 5000}
    entry = {
        "timestamp": _ts(60),
        "input_tokens": 100,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 5000,
    }
    assert _classify_turn(entry, prev_entry=prev, threshold=1024) == "miss_invalidation"


def test_classify_invalidation_handles_alt_timestamp_field() -> None:
    """Test fixtures use 'ts'; telemetry writes 'timestamp' — both must work."""
    prev = {"ts": _ts(0), "input_tokens": 100, "cache_read_tokens": 5000}
    entry = {
        "ts": _ts(60),
        "input_tokens": 100,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 5000,
    }
    assert _classify_turn(entry, prev_entry=prev, threshold=1024) == "miss_invalidation"


# The `diagnose_cache(metrics_path, ...)` I/O tests that used to live below were
# removed with that function (PLAN-harness-economics-observability ADR-005): once
# telemetry stopped writing the token fields it would have returned `no_data`
# unconditionally and forever. Its behavioural coverage now lives in
# tests/unit/test_cache_diagnostics_transcript.py against the pure
# `diagnose_cache_from_turns` core. The pure-function tests above are UNCHANGED —
# three of them are pinned by node id in specs/SPEC-cache-diagnostics.machine.yaml.
