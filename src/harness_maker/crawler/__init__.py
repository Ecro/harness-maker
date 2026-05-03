"""Crawler package — anti-rot pipeline 4-source HTTP fetchers.

Each submodule exposes ``crawl(...) -> list[CrawlItem]`` and must:
  * accept an injectable HTTP client / parser to enable unit-test mocking,
  * catch network errors gracefully (return empty list, log to stderr),
  * never perform real HTTP at import time.

Use ``write_raw(items, project_dir)`` to dump a daily JSONL snapshot under
``<project_dir>/.claude/observability/refresh/raw-<YYYY-MM-DD>.jsonl``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from harness_maker.crawler import anthropic_blog, arxiv, github_releases, osv_dev
from harness_maker.models import CrawlItem

__all__ = [
    "anthropic_blog",
    "arxiv",
    "github_releases",
    "osv_dev",
    "write_raw",
]


def write_raw(items: list[CrawlItem], project_dir: Path | str) -> Path:
    """Write CrawlItems as a daily JSONL snapshot under observability/refresh/.

    Truncates per call (daily-snapshot semantics). Re-running on the same day
    overwrites the previous snapshot rather than duplicating items. Creates the
    directory if missing. Returns the path written.
    """
    project = Path(project_dir)
    out_dir = project / ".claude" / "observability" / "refresh"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"raw-{date.today().isoformat()}.jsonl"
    with out_path.open("w", encoding="utf-8") as fp:
        for item in items:
            fp.write(item.model_dump_json())
            fp.write("\n")
    return out_path
