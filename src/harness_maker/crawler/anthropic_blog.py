"""Anthropic news/blog scraper (HTML → CrawlItem).

Anthropic does not publish an RSS feed for ``/news`` so this module fetches the
HTML index page and extracts ``<article>``-style cards via BeautifulSoup.
Returns up to 20 items. All HTTP is performed via an injectable
``httpx.Client`` to keep unit tests offline.
"""

from __future__ import annotations

import sys

import httpx
from bs4 import BeautifulSoup, Tag

from harness_maker.models import CrawlItem

NEWS_URL = "https://www.anthropic.com/news"
SOURCE = "anthropic_blog"
MAX_ITEMS = 20
DEFAULT_TIMEOUT = 10.0


def crawl(client: httpx.Client | None = None) -> list[CrawlItem]:
    """Fetch the Anthropic news index and return up to ``MAX_ITEMS`` CrawlItems.

    Network and parsing errors are caught and logged to stderr; an empty list is
    returned in those cases.
    """
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True)
    try:
        try:
            response = client.get(NEWS_URL)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            print(f"[anthropic_blog] HTTP error: {exc}", file=sys.stderr)
            return []
        try:
            return _parse_html(response.text)
        except Exception as exc:  # noqa: BLE001 — defensive, log and skip
            print(f"[anthropic_blog] parse error: {exc}", file=sys.stderr)
            return []
    finally:
        if owns_client:
            client.close()


def _parse_html(html: str) -> list[CrawlItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[CrawlItem] = []
    seen: set[str] = set()

    # Strategy: every internal /news/<slug> link with a non-trivial title is a card.
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href_attr = anchor.get("href")
        if not isinstance(href_attr, str):
            continue
        href = href_attr.strip()
        if not href.startswith("/news/") or href == "/news/":
            continue
        if href in seen:
            continue
        title = _extract_title(anchor)
        if not title:
            continue
        seen.add(href)
        url = "https://www.anthropic.com" + href
        items.append(
            CrawlItem(
                source=SOURCE,
                item_id=url,
                title=title,
                summary=_extract_summary(anchor),
                published=None,
                metadata={"url": url, "href": href},
            )
        )
        if len(items) >= MAX_ITEMS:
            break
    return items


def _extract_title(anchor: Tag) -> str:
    """Pull a clean title string from an anchor's children."""
    # Prefer an explicit heading element.
    for tag_name in ("h1", "h2", "h3", "h4"):
        heading = anchor.find(tag_name)
        if isinstance(heading, Tag):
            text = heading.get_text(" ", strip=True)
            if text:
                return text
    # Fall back to the anchor's own text.
    return anchor.get_text(" ", strip=True)


def _extract_summary(anchor: Tag) -> str:
    """Extract a short summary if a sibling/descendant <p> is present."""
    paragraph = anchor.find("p")
    if not isinstance(paragraph, Tag):
        return ""
    return paragraph.get_text(" ", strip=True)
