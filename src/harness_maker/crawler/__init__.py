"""Crawler package — OSV CVE fetcher only (ADR-0007).

ADR-0007 (0.22.3) removed 3 of the 4 original crawl sources alongside the
``/hm:health`` external_risks layer. Only ``osv_dev`` survives because
``secscan/dependency_cves.py`` (consumed by ``/hm:verify``) still relies
on it for dependency CVE detection — a different, narrower channel than
the deleted anti-rot push.

The module exposes ``crawl(...) -> list[CrawlItem]`` and must:
  * accept an injectable HTTP client / parser to enable unit-test mocking,
  * catch network errors gracefully (return empty list, log to stderr),
  * never perform real HTTP at import time.
"""

from __future__ import annotations

from harness_maker.crawler import osv_dev

__all__ = ["osv_dev"]
