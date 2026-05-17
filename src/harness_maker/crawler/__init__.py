"""Crawler package — anti-rot pipeline 4-source HTTP fetchers.

Each submodule exposes ``crawl(...) -> list[CrawlItem]`` and must:
  * accept an injectable HTTP client / parser to enable unit-test mocking,
  * catch network errors gracefully (return empty list, log to stderr),
  * never perform real HTTP at import time.

Use ``write_raw(items, project_dir)`` to dump a daily JSONL snapshot under
``<project_dir>/.claude/observability/health/raw-<YYYY-MM-DD>.jsonl``.

The runtime directory was renamed from ``observability/refresh/`` to
``observability/health/`` in 0.13.0 (PLAN health-consolidation Phase 1 /
ADR-004 — hard cut, no shim). ``observability/adaptive/`` is UNCHANGED.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from harness_maker.cache import SOURCE_TTLS, HttpCache
from harness_maker.crawler import anthropic_blog, arxiv, github_releases, osv_dev
from harness_maker.io_utils import atomic_write
from harness_maker.models import CrawlItem

__all__ = [
    "anthropic_blog",
    "arxiv",
    "github_releases",
    "osv_dev",
    "write_raw",
    "crawl_all_cached",
]


def write_raw(items: list[CrawlItem], project_dir: Path | str) -> Path:
    """Write CrawlItems as a daily JSONL snapshot under observability/health/.

    Truncates per call (daily-snapshot semantics). Re-running on the same day
    overwrites the previous snapshot rather than duplicating items. Creates the
    directory if missing. Returns the path written.
    """
    project = Path(project_dir)
    out_dir = project / ".claude" / "observability" / "health"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"raw-{date.today().isoformat()}.jsonl"
    content = "".join(item.model_dump_json() + "\n" for item in items)
    atomic_write(out_path, content)
    return out_path


def crawl_all_cached(
    *,
    cache_base: Path | None = None,
) -> list[CrawlItem]:
    """Run all 4 crawlers with HTTP-level caching.

    On cache hit (within source TTL), returns deserialized CrawlItems
    without making any HTTP calls. On miss, calls the real crawler and
    caches the result.
    """
    all_items: list[CrawlItem] = []

    sources = [
        ("anthropic_blog", lambda: [i.model_dump() for i in anthropic_blog.crawl()]),
        ("github_releases", lambda: [i.model_dump() for i in github_releases.crawl()]),
        ("arxiv", lambda: [i.model_dump() for i in arxiv.crawl()]),
        ("osv_dev", lambda: [i.model_dump() for i in osv_dev.crawl()]),
    ]

    for source_name, fetcher in sources:
        cache = HttpCache(source_name, base_dir=cache_base)
        ttl = SOURCE_TTLS.get(source_name, 3600.0)
        try:
            raw = cache.get_or_fetch("latest", fetcher, ttl)
            if isinstance(raw, list):
                all_items.extend(CrawlItem(**d) for d in raw if isinstance(d, dict))
        except Exception as exc:  # noqa: BLE001
            print(f"[crawler:{source_name}] cache/fetch error: {exc}", file=sys.stderr)

    return all_items
