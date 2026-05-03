"""arxiv crawler tests — feedparser monkeypatched, no real network."""

from __future__ import annotations

from typing import Any

import pytest

from harness_maker.crawler import arxiv


def _fake_feed(entries: list[dict[str, Any]]) -> Any:
    feed = type("Feed", (), {})()
    feed.entries = entries  # type: ignore[attr-defined]
    return feed


def test_crawl_returns_items_from_mocked_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_url: list[str] = []

    def fake_parse(url: str) -> Any:
        captured_url.append(url)
        return _fake_feed(
            [
                {
                    "title": "A novel coding agent benchmark",
                    "id": "http://arxiv.org/abs/2604.00001v1",
                    "summary": "We propose ...",
                    "published": "2026-04-01T00:00:00Z",
                },
                {
                    "title": "Prompt injection at scale",
                    "id": "http://arxiv.org/abs/2604.00002v1",
                    "summary": "We study ...",
                    "published": "2026-04-02T00:00:00Z",
                },
            ]
        )

    monkeypatch.setattr(arxiv.feedparser, "parse", fake_parse)
    items = arxiv.crawl("cat:cs.SE")

    assert len(items) == 2
    assert items[0].source == "arxiv"
    assert items[0].title == "A novel coding agent benchmark"
    assert items[0].item_id.startswith("http://arxiv.org/abs/")
    assert "search_query=cat" in captured_url[0]


def test_crawl_skips_entries_missing_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        arxiv.feedparser,
        "parse",
        lambda _u: _fake_feed([{"summary": "no title or id"}]),
    )
    items = arxiv.crawl()
    assert items == []


def test_crawl_returns_empty_on_parser_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_url: str) -> Any:
        raise RuntimeError("network down")

    monkeypatch.setattr(arxiv.feedparser, "parse", boom)
    items = arxiv.crawl()
    assert items == []
