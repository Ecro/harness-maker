"""GitHub releases crawler tests — HTTP mocked via httpx.MockTransport."""

from __future__ import annotations

import json

import httpx

from harness_maker.crawler import github_releases

SAMPLE_RELEASES = [
    {
        "html_url": "https://github.com/anthropics/claude-code/releases/tag/v1.2.3",
        "name": "v1.2.3",
        "tag_name": "v1.2.3",
        "body": "First release line.\nMore details.",
        "published_at": "2026-04-01T00:00:00Z",
        "draft": False,
        "prerelease": False,
    },
    {
        "html_url": "https://github.com/anthropics/claude-code/releases/tag/v1.2.4",
        "name": "v1.2.4",
        "tag_name": "v1.2.4",
        "body": "",
        "published_at": "2026-04-02T00:00:00Z",
        "draft": False,
        "prerelease": True,
    },
]


def _client_returning(payload: object, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.github.com"
        return httpx.Response(status, content=json.dumps(payload).encode())

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_crawl_returns_items_for_each_release() -> None:
    client = _client_returning(SAMPLE_RELEASES)
    items = github_releases.crawl(repos=["anthropics/claude-code"], client=client)

    assert len(items) == 2
    assert all(item.source == "github_releases" for item in items)
    titles = [item.title for item in items]
    assert "anthropics/claude-code v1.2.3" in titles
    assert items[0].summary == "First release line."
    assert items[0].metadata["repo"] == "anthropics/claude-code"
    assert items[1].metadata["prerelease"] is True


def test_crawl_handles_rate_limit() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="API rate limit exceeded for 1.2.3.4.")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    items = github_releases.crawl(repos=["any/repo"], client=client)
    assert items == []


def test_crawl_handles_non_200() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    items = github_releases.crawl(repos=["missing/repo"], client=client)
    assert items == []


def test_crawl_uses_default_repos_when_none() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, content=b"[]")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    items = github_releases.crawl(client=client)
    assert items == []
    assert captured, "should have hit the API at least once"
    assert "anthropics/claude-code" in captured[0]
