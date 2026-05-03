"""Relevance filter tests — adaptive threshold + keyword scorer."""

from __future__ import annotations

import pytest

from harness_maker.models import CrawlItem
from harness_maker.relevance import (
    DEFAULT_THRESHOLD,
    THRESHOLD_MAX,
    THRESHOLD_MIN,
    adaptive_threshold,
    filter_items,
    score,
    score_item,
)

# ─── adaptive_threshold ───────────────────────────────────────────────────────


def test_adaptive_threshold_empty_history_returns_default() -> None:
    assert adaptive_threshold([]) == DEFAULT_THRESHOLD


def test_adaptive_threshold_below_min_samples_returns_default() -> None:
    assert adaptive_threshold([True, True, False]) == DEFAULT_THRESHOLD


def test_adaptive_threshold_high_accept_rate_relaxes() -> None:
    history = [True] * 20  # 100% accept
    assert adaptive_threshold(history) < DEFAULT_THRESHOLD
    assert adaptive_threshold(history) >= THRESHOLD_MIN


def test_adaptive_threshold_low_accept_rate_tightens() -> None:
    history = [False] * 20  # 0% accept
    assert adaptive_threshold(history) > DEFAULT_THRESHOLD
    assert adaptive_threshold(history) <= THRESHOLD_MAX


def test_adaptive_threshold_mixed_returns_default() -> None:
    history = [True, False, True, False, True, False, True]  # ~50/50
    # accept_rate = 4/7 ≈ 0.57 — neither >0.8 nor <0.5
    assert adaptive_threshold(history) == DEFAULT_THRESHOLD


def test_adaptive_threshold_uses_only_recent_window() -> None:
    # 100 rejects (history) + 20 accepts (recent). Should respond to recent only.
    history = [False] * 100 + [True] * 20
    assert adaptive_threshold(history) < DEFAULT_THRESHOLD


def test_adaptive_threshold_clamped_to_min() -> None:
    history = [True] * 50
    assert adaptive_threshold(history) >= THRESHOLD_MIN


def test_adaptive_threshold_clamped_to_max() -> None:
    history = [False] * 50
    assert adaptive_threshold(history) <= THRESHOLD_MAX


# ─── score_item ───────────────────────────────────────────────────────────────


def _item(title: str = "", summary: str = "") -> CrawlItem:
    return CrawlItem(source="test", item_id="x", title=title, summary=summary)


def test_score_item_no_keywords_returns_zero() -> None:
    assert score_item(_item("hello world"), []) == 0.0


def test_score_item_full_overlap_returns_one() -> None:
    item = _item("Claude code agent harness", "with prompt engineering")
    keywords = ["claude", "harness"]
    assert score_item(item, keywords) == 1.0


def test_score_item_partial_overlap() -> None:
    item = _item("agent harness", "")
    keywords = ["agent", "ux", "perf"]  # 1 of 3 matches
    assert score_item(item, keywords) == pytest.approx(1 / 3)


def test_score_item_no_overlap_returns_zero() -> None:
    item = _item("totally unrelated", "nothing matches")
    assert score_item(item, ["foo", "bar"]) == 0.0


def test_score_item_case_insensitive() -> None:
    item = _item("CLAUDE Code", "")
    assert score_item(item, ["claude"]) == 1.0


def test_score_alias_matches_score_item() -> None:
    item = _item("agent harness", "")
    assert score(item, ["agent"]) == score_item(item, ["agent"])


# ─── filter_items ─────────────────────────────────────────────────────────────


def test_filter_items_threshold_inclusive() -> None:
    items = [
        CrawlItem(source="t", item_id="a", title="A", score=0.9),
        CrawlItem(source="t", item_id="b", title="B", score=0.7),
        CrawlItem(source="t", item_id="c", title="C", score=0.5),
    ]
    out = filter_items(items, 0.7)
    ids = [i.item_id for i in out]
    assert ids == ["a", "b"]


def test_filter_items_empty_input() -> None:
    assert filter_items([], 0.5) == []


def test_filter_items_all_below_threshold() -> None:
    items = [CrawlItem(source="t", item_id="a", title="A", score=0.1)]
    assert filter_items(items, 0.7) == []
