"""GitHub releases crawler — fetches /repos/{owner}/{repo}/releases for each repo.

Honors ``GITHUB_TOKEN`` env var when present (lifts the unauthenticated
60 req/hour rate limit). All HTTP is performed via an injectable
``httpx.Client``. Network/rate-limit failures degrade to an empty list with a
stderr warning.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx

from harness_maker.models import CrawlItem

SOURCE = "github_releases"
DEFAULT_REPOS: list[str] = ["anthropics/claude-code"]
DEFAULT_TIMEOUT = 10.0
PER_REPO_LIMIT = 10  # cap items returned per repo to avoid balloons


def crawl(
    repos: list[str] | None = None,
    client: httpx.Client | None = None,
) -> list[CrawlItem]:
    """Fetch releases for each ``owner/repo`` and return CrawlItems."""
    repos = repos if repos is not None else DEFAULT_REPOS
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True)
    headers = _build_headers()
    items: list[CrawlItem] = []
    try:
        for repo in repos:
            items.extend(_fetch_repo(repo, client, headers))
    finally:
        if owns_client:
            client.close()
    return items


def _build_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "harness-maker-crawler",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_repo(repo: str, client: httpx.Client, headers: dict[str, str]) -> list[CrawlItem]:
    url = f"https://api.github.com/repos/{repo}/releases"
    try:
        response = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        print(f"[github_releases] HTTP error for {repo}: {exc}", file=sys.stderr)
        return []
    if response.status_code == 403 and "rate limit" in response.text.lower():
        print(f"[github_releases] rate-limited on {repo}", file=sys.stderr)
        return []
    if response.status_code >= 400:
        print(
            f"[github_releases] HTTP {response.status_code} for {repo}",
            file=sys.stderr,
        )
        return []
    try:
        payload = response.json()
    except ValueError as exc:
        print(f"[github_releases] JSON decode error for {repo}: {exc}", file=sys.stderr)
        return []
    if not isinstance(payload, list):
        return []
    items: list[CrawlItem] = []
    for raw in payload[:PER_REPO_LIMIT]:
        item = _to_item(repo, raw)
        if item is not None:
            items.append(item)
    return items


def _to_item(repo: str, raw: dict[str, Any]) -> CrawlItem | None:
    if not isinstance(raw, dict):
        return None
    html_url = raw.get("html_url") or raw.get("url") or ""
    if not html_url:
        return None
    name = raw.get("name") or raw.get("tag_name") or "(unnamed release)"
    body = raw.get("body") or ""
    if not isinstance(body, str):
        body = str(body)
    summary = body.strip().splitlines()[0] if body.strip() else ""
    return CrawlItem(
        source=SOURCE,
        item_id=str(html_url),
        title=f"{repo} {name}",
        summary=summary[:500],
        published=raw.get("published_at"),
        metadata={
            "repo": repo,
            "tag": raw.get("tag_name"),
            "url": html_url,
            "draft": bool(raw.get("draft", False)),
            "prerelease": bool(raw.get("prerelease", False)),
        },
    )
