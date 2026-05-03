"""Anthropic blog crawler tests — all HTTP mocked via httpx.MockTransport."""

from __future__ import annotations

import httpx

from harness_maker.crawler import anthropic_blog

SAMPLE_HTML = """
<!doctype html>
<html><body>
  <a href="/news/article-one"><h2>Article One</h2><p>First summary.</p></a>
  <a href="/news/article-two"><h2>Article Two</h2><p>Second summary.</p></a>
  <a href="/news/article-one"><h2>Article One Duplicate</h2></a>
  <a href="/careers"><h2>Should be ignored</h2></a>
  <a href="/news/"><h2>Index, also ignored</h2></a>
</body></html>
"""


def _client_returning(html: str, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.anthropic.com"
        return httpx.Response(status, text=html)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_crawl_returns_items_from_mocked_html() -> None:
    client = _client_returning(SAMPLE_HTML)
    items = anthropic_blog.crawl(client=client)

    assert len(items) == 2
    assert all(item.source == "anthropic_blog" for item in items)

    titles = [item.title for item in items]
    assert "Article One" in titles
    assert "Article Two" in titles
    assert all(item.item_id.startswith("https://www.anthropic.com/news/") for item in items)
    assert any(item.summary == "First summary." for item in items)


def test_crawl_returns_empty_list_on_http_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    items = anthropic_blog.crawl(client=client)
    assert items == []


def test_crawl_caps_at_max_items() -> None:
    many = "".join(
        f'<a href="/news/post-{i}"><h2>Post {i}</h2></a>'
        for i in range(50)
    )
    html = f"<html><body>{many}</body></html>"
    client = _client_returning(html)
    items = anthropic_blog.crawl(client=client)
    assert len(items) == anthropic_blog.MAX_ITEMS
