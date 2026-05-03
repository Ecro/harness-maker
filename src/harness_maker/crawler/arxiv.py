"""arxiv crawler — uses ``feedparser`` against the public Atom query API.

Tests monkeypatch ``feedparser.parse`` to avoid real network. Failures degrade
to an empty list with a stderr warning.
"""

from __future__ import annotations

import sys
import urllib.parse
from typing import Any

import feedparser  # type: ignore[import-untyped]

from harness_maker.models import CrawlItem

SOURCE = "arxiv"
ARXIV_API = "https://export.arxiv.org/api/query"
DEFAULT_QUERY = "cat:cs.AI"
MAX_RESULTS = 25


def crawl(query: str = DEFAULT_QUERY) -> list[CrawlItem]:
    """Fetch arxiv results for ``query`` and return CrawlItems.

    ``query`` follows arxiv search_query syntax (e.g. ``cat:cs.AI`` or
    ``ti:agent AND cat:cs.SE``).
    """
    url = _build_url(query)
    try:
        feed: Any = feedparser.parse(url)
    except Exception as exc:  # noqa: BLE001 — defensive
        print(f"[arxiv] parse error: {exc}", file=sys.stderr)
        return []
    entries = getattr(feed, "entries", None)
    if entries is None and isinstance(feed, dict):
        entries = feed.get("entries", [])
    entries = entries or []
    items: list[CrawlItem] = []
    for entry in entries:
        item = _to_item(entry)
        if item is not None:
            items.append(item)
    return items


def _build_url(query: str) -> str:
    params = {
        "search_query": query,
        "start": "0",
        "max_results": str(MAX_RESULTS),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return f"{ARXIV_API}?{urllib.parse.urlencode(params)}"


def _to_item(entry: Any) -> CrawlItem | None:
    title = _entry_field(entry, "title")
    link = _entry_field(entry, "id") or _entry_field(entry, "link")
    if not title or not link:
        return None
    summary = _entry_field(entry, "summary") or ""
    published = _entry_field(entry, "published") or _entry_field(entry, "updated")
    return CrawlItem(
        source=SOURCE,
        item_id=link,
        title=title.strip(),
        summary=summary.strip()[:1000],
        published=published,
        metadata={"url": link},
    )


def _entry_field(entry: Any, name: str) -> str | None:
    """Read a field from a feedparser entry which may behave like dict or attr-bag."""
    value: Any = entry.get(name) if isinstance(entry, dict) else getattr(entry, name, None)
    if value is None:
        return None
    return str(value)
