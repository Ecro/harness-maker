"""Cache diagnostics — failure-mode classification and scoring."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker.cache_diagnostics import (
    CacheDiagnosis,
    _classify_turn,
    _score_from_hit_rate,
    _threshold_for_model,
    diagnose_cache,
)


def _write_metrics(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def _ts(offset_seconds: int = 0) -> str:
    return (
        datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC) + timedelta(seconds=offset_seconds)
    ).isoformat()


# ── _threshold_for_model ────────────────────────────────────────────────────


def test_threshold_haiku_is_4096() -> None:
    assert _threshold_for_model("claude-haiku-4-5") == 4096


def test_threshold_sonnet_is_1024() -> None:
    assert _threshold_for_model("claude-sonnet-4-6") == 1024


def test_threshold_opus_is_1024() -> None:
    assert _threshold_for_model("claude-opus-4-7") == 1024


def test_threshold_unknown_falls_back_to_1024() -> None:
    assert _threshold_for_model("gpt-4") == 1024


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


# ── diagnose_cache: I/O edge cases ──────────────────────────────────────────


def test_diagnose_no_file(tmp_path: Path) -> None:
    res = diagnose_cache(tmp_path / "missing.jsonl")
    assert res.primary_failure == "no_data"
    assert res.score == 50
    assert res.sample_size == 0


def test_diagnose_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    p.write_text("", encoding="utf-8")
    res = diagnose_cache(p)
    assert res.primary_failure == "no_data"


def test_diagnose_skips_malformed_lines(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    p.write_text(
        "\n".join(
            [
                "not json",
                json.dumps({"input_tokens": 100, "cache_read_tokens": 5000}),
                "{partial",
                "[1,2]",  # not a dict
            ]
        ),
        encoding="utf-8",
    )
    res = diagnose_cache(p)
    assert res.sample_size == 1
    assert res.hit_rate == 100


# ── diagnose_cache: scenarios ───────────────────────────────────────────────


def test_diagnose_all_hits(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    _write_metrics(
        p,
        [
            {
                "timestamp": _ts(i * 30),
                "input_tokens": 100,
                "cache_read_tokens": 5000,
                "cache_creation_tokens": 0,
            }
            for i in range(10)
        ],
    )
    res = diagnose_cache(p)
    assert res.hit_rate == 100
    assert res.score == 100
    assert res.primary_failure is None


def test_diagnose_min_threshold_dominant(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    _write_metrics(
        p,
        [
            {
                "timestamp": _ts(i * 30),
                "input_tokens": 500,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
            }
            for i in range(8)
        ],
    )
    res = diagnose_cache(p)
    assert res.primary_failure == "miss_min_threshold"
    assert res.hit_rate == 0
    assert "1024 tokens" in res.evidence
    assert "Bulk up the static prefix" in res.remediation


def test_diagnose_ttl_dominant(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    # alternating long gaps; first turn doesn't count as TTL
    entries = []
    for i in range(6):
        entries.append(
            {
                "timestamp": _ts(i * 600),  # 10-min gaps
                "input_tokens": 500,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 5000,
            }
        )
    _write_metrics(p, entries)
    res = diagnose_cache(p)
    assert res.primary_failure == "miss_ttl"
    assert "5 min gap" in res.evidence


def test_diagnose_invalidation_dominant(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    # Tight gaps but cache always re-written → invalidation
    entries = [
        {
            "timestamp": _ts(i * 30),
            "input_tokens": 500,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 5000,
        }
        for i in range(6)
    ]
    _write_metrics(p, entries)
    res = diagnose_cache(p)
    assert res.primary_failure == "miss_invalidation"
    assert "prefix changed" in res.evidence


def test_diagnose_haiku_uses_4096_threshold(tmp_path: Path) -> None:
    """A 2000-token prefix is fine for Sonnet but below Haiku's 4096 threshold."""
    p = tmp_path / "metrics.jsonl"
    _write_metrics(
        p,
        [
            {
                "timestamp": _ts(i * 30),
                "input_tokens": 2000,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
            }
            for i in range(5)
        ],
    )
    res = diagnose_cache(p, model="claude-haiku-4-5")
    assert res.primary_failure == "miss_min_threshold"
    assert "4096" in res.evidence


def test_diagnose_window_caps_sample_size(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    _write_metrics(
        p,
        [
            {"timestamp": _ts(i * 30), "input_tokens": 100, "cache_read_tokens": 5000}
            for i in range(200)
        ],
    )
    res = diagnose_cache(p, window=50)
    assert res.sample_size == 50


def test_diagnose_returns_pydantic_model(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    _write_metrics(p, [{"timestamp": _ts(0), "input_tokens": 100, "cache_read_tokens": 5000}])
    res = diagnose_cache(p)
    assert isinstance(res, CacheDiagnosis)
    assert isinstance(res.counters, dict)


def test_diagnose_counters_contain_all_classes(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    _write_metrics(
        p,
        [
            # First turn: creation > 0, prev None → miss_first
            {
                "timestamp": _ts(0),
                "input_tokens": 200,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 5000,
            },
            # Second turn: hit
            {
                "timestamp": _ts(60),
                "input_tokens": 200,
                "cache_read_tokens": 5000,
                "cache_creation_tokens": 0,
            },
        ],
    )
    res = diagnose_cache(p)
    assert res.counters["hit"] == 1
    assert res.counters["miss_first"] == 1


# ── 0.5.4 hybrid telemetry: filter `event != post_tool_use` entries ─────────


def test_diagnose_filters_cursor_stop_entries(tmp_path: Path) -> None:
    """Cursor stop entries (event=stop, no token fields) must NOT pollute
    the cache classification — they would all bucket as miss_min_threshold
    (input_tokens=0 < threshold) and drag hit-rate to 0%."""
    p = tmp_path / "metrics.jsonl"
    _write_metrics(
        p,
        [
            # 5 real tool calls, all hits
            *(
                {
                    "timestamp": _ts(i * 30),
                    "event": "post_tool_use",
                    "tool_name": "Read",
                    "input_tokens": 200,
                    "cache_read_tokens": 5000,
                }
                for i in range(5)
            ),
            # 20 Cursor stop entries interspersed — must be ignored
            *(
                {
                    "timestamp": _ts(150 + i),
                    "event": "stop",
                    "status": "completed",
                    "loop_count": i,
                }
                for i in range(20)
            ),
        ],
    )
    res = diagnose_cache(p)
    assert res.sample_size == 5  # only post_tool_use entries counted
    assert res.hit_rate == 100  # not diluted by stop entries


def test_diagnose_returns_no_data_when_only_stop_entries(tmp_path: Path) -> None:
    """Pure Cursor session (only stop events, no token data) → no_data
    diagnosis with Cursor-specific guidance, not silent miss bucket."""
    p = tmp_path / "metrics.jsonl"
    _write_metrics(
        p,
        [
            {
                "timestamp": _ts(i * 30),
                "event": "stop",
                "status": "completed",
                "loop_count": i,
            }
            for i in range(10)
        ],
    )
    res = diagnose_cache(p)
    assert res.sample_size == 0
    assert res.primary_failure == "no_data"
    assert "cursor" in res.evidence.lower()


def test_diagnose_treats_untagged_entries_as_post_tool_use(tmp_path: Path) -> None:
    """Pre-0.5.4 metrics files lack the `event` field. Backward compat:
    treat untagged entries as post_tool_use (their original purpose)."""
    p = tmp_path / "metrics.jsonl"
    _write_metrics(
        p,
        [
            {
                "timestamp": _ts(i * 30),
                # NO event field — pre-0.5.4 schema
                "tool_name": "Read",
                "input_tokens": 200,
                "cache_read_tokens": 5000,
            }
            for i in range(5)
        ],
    )
    res = diagnose_cache(p)
    assert res.sample_size == 5
    assert res.hit_rate == 100
