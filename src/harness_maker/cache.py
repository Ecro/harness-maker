"""HTTP response / crawl-result cache with TTL.

Generic cache for expensive fetcher operations (HTTP crawlers, API calls).
Results are stored as JSON under ``~/.cache/harness-maker/<source>/`` with
per-entry TTL. Respects ``HARNESS_MAKER_CACHE_DIR`` env override (ADR-003).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from harness_maker.io_utils import atomic_write

T = TypeVar("T")


def _cache_base() -> Path:
    override = os.environ.get("HARNESS_MAKER_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "harness-maker"


class HttpCache:
    """Filesystem-backed cache with per-entry TTL.

    ``get_or_fetch(key, fetcher, ttl)`` returns cached data when
    the entry is younger than ``ttl`` seconds; otherwise calls
    ``fetcher()``, caches the result, and returns it.
    """

    def __init__(self, source: str, base_dir: Path | None = None) -> None:
        self._base = (base_dir or _cache_base()) / source
        self._base.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self._base / f"{safe_key}.json"

    def get(self, key: str, ttl: float) -> Any | None:
        """Return cached value if fresh (within TTL), else None."""
        path = self._entry_path(key)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > ttl:
            return None
        return data.get("value")

    def put(self, key: str, value: Any) -> None:
        """Store a value with the current timestamp."""
        path = self._entry_path(key)
        entry = {"cached_at": time.time(), "value": value}
        atomic_write(path, json.dumps(entry, ensure_ascii=False) + "\n")

    def get_or_fetch(
        self,
        key: str,
        fetcher: Callable[[], T],
        ttl: float,
    ) -> T:
        """Return cached value if fresh, else call fetcher and cache result."""
        cached = self.get(key, ttl)
        if cached is not None:
            return cached  # type: ignore[return-value]
        result = fetcher()
        self.put(key, result)
        return result

    def invalidate(self, key: str) -> None:
        """Remove a cached entry."""
        path = self._entry_path(key)
        path.unlink(missing_ok=True)


TTL_1H = 3600.0
TTL_24H = 86400.0

SOURCE_TTLS: dict[str, float] = {
    "anthropic_blog": TTL_24H,
    "github_releases": TTL_1H,
    "arxiv": TTL_24H,
    "osv_dev": TTL_1H,
}
