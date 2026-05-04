"""Relevance filter tests — adaptive threshold + keyword + LLM scorer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.models import CrawlItem
from harness_maker.relevance import (
    DEFAULT_THRESHOLD,
    THRESHOLD_MAX,
    THRESHOLD_MIN,
    adaptive_threshold,
    extract_project_context,
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


# ─── LLM scorer ───────────────────────────────────────────────────────────────


class _FakeJudge:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def judge(self, system: str, user: str, model: str) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_score_item_llm_returns_normalized_score() -> None:
    item = _item("agentic AI", "Claude Code subagent guide")
    fake = _FakeJudge(json.dumps({"score": 0.87, "rationale": "directly applicable"}))
    s = score_item(item, project_context="ctx", client=fake)
    assert s == pytest.approx(0.87)
    assert len(fake.calls) == 1


def test_score_item_llm_clamps_out_of_range() -> None:
    item = _item("x", "y")
    fake = _FakeJudge(json.dumps({"score": 1.5, "rationale": "too high"}))
    assert score_item(item, project_context="ctx", client=fake) == 1.0


def test_score_item_llm_falls_back_on_invalid_json() -> None:
    item = _item("agent", "")
    fake = _FakeJudge("not valid json")
    s = score_item(item, ["agent"], project_context="ctx", client=fake)
    assert s == 1.0  # keyword fallback hit


def test_score_item_llm_falls_back_on_client_error() -> None:
    item = _item("agent harness", "")
    fake = _FakeJudge(RuntimeError("rate limited"))
    s = score_item(item, ["agent"], project_context="ctx", client=fake)
    assert s == pytest.approx(1.0)


def test_score_item_llm_caches_system_prompt_across_calls() -> None:
    """Same project_context → identical system prompt across items (cache-friendly)."""
    fake = _FakeJudge(json.dumps({"score": 0.5, "rationale": "x"}))
    item_a = _item("a", "")
    item_b = _item("b", "")
    score_item(item_a, project_context="my-ctx", client=fake)
    score_item(item_b, project_context="my-ctx", client=fake)
    assert fake.calls[0]["system"] == fake.calls[1]["system"]
    assert fake.calls[0]["user"] != fake.calls[1]["user"]


def test_score_item_no_client_uses_keyword_fallback() -> None:
    item = _item("python claude", "")
    assert score_item(item, ["python"]) == 1.0


def test_score_item_no_project_context_uses_keyword_fallback() -> None:
    fake = _FakeJudge(json.dumps({"score": 0.99}))
    item = _item("python", "")
    s = score_item(item, ["python"], project_context="", client=fake)
    assert s == 1.0  # context empty → skipped LLM, fell to keywords
    assert fake.calls == []


def test_score_item_llm_missing_score_field_falls_back() -> None:
    fake = _FakeJudge(json.dumps({"rationale": "no score"}))
    item = _item("agent", "")
    s = score_item(item, ["agent"], project_context="ctx", client=fake)
    assert s == 1.0  # fell to keyword


def test_score_item_llm_strips_markdown_fence() -> None:
    raw = '```json\n{"score": 0.42, "rationale": "ok"}\n```'
    fake = _FakeJudge(raw)
    s = score_item(_item("x", "y"), project_context="ctx", client=fake)
    assert s == pytest.approx(0.42)


# ─── extract_project_context ──────────────────────────────────────────────────


def test_extract_context_combines_claude_md_and_readme(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# project\nstack: python\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# readme\nshort description\n", encoding="utf-8")
    ctx = extract_project_context(tmp_path)
    assert "CLAUDE.md" in ctx
    assert "README.md" in ctx
    assert "stack: python" in ctx


def test_extract_context_empty_when_no_docs(tmp_path: Path) -> None:
    assert extract_project_context(tmp_path) == ""


def test_extract_context_caps_long_files(tmp_path: Path) -> None:
    long = "x" * 10000
    (tmp_path / "CLAUDE.md").write_text(long, encoding="utf-8")
    ctx = extract_project_context(tmp_path)
    # 2KB cap per file, plus header overhead
    assert len(ctx) < 2500
