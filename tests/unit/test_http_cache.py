"""Tests for HTTP cache + crawler integration (Phase 4)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from harness_maker.cache import SOURCE_TTLS, TTL_1H, HttpCache


def test_http_cache_ttl(tmp_path: Path) -> None:
    """Cached entry must be returned within TTL, missed after expiry."""
    cache = HttpCache("test-source", base_dir=tmp_path)

    call_count = 0

    def fetcher() -> list[str]:
        nonlocal call_count
        call_count += 1
        return ["item1", "item2"]

    result1 = cache.get_or_fetch("key1", fetcher, ttl=10.0)
    assert result1 == ["item1", "item2"]
    assert call_count == 1

    result2 = cache.get_or_fetch("key1", fetcher, ttl=10.0)
    assert result2 == ["item1", "item2"]
    assert call_count == 1  # fetcher NOT called again — cache hit

    cache.invalidate("key1")
    result3 = cache.get_or_fetch("key1", fetcher, ttl=10.0)
    assert result3 == ["item1", "item2"]
    assert call_count == 2  # fetcher called again after invalidation


def test_http_cache_ttl_expiry(tmp_path: Path) -> None:
    """Cache miss when entry is older than TTL."""
    cache = HttpCache("test-source", base_dir=tmp_path)
    cache.put("old-key", "old-value")

    entry_path = cache._entry_path("old-key")
    data = json.loads(entry_path.read_text(encoding="utf-8"))
    data["cached_at"] = time.time() - 100
    entry_path.write_text(json.dumps(data), encoding="utf-8")

    assert cache.get("old-key", ttl=50.0) is None
    assert cache.get("old-key", ttl=200.0) == "old-value"


def test_http_cache_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HARNESS_MAKER_CACHE_DIR env var overrides the default cache base."""
    custom_dir = tmp_path / "custom"
    monkeypatch.setenv("HARNESS_MAKER_CACHE_DIR", str(custom_dir))

    from harness_maker.cache import _cache_base

    result = _cache_base()
    assert result == custom_dir


def test_source_ttls_defined() -> None:
    """OSV crawler source has a TTL definition (ADR-0007 removed the other 3)."""
    assert "osv_dev" in SOURCE_TTLS
    assert SOURCE_TTLS["osv_dev"] == TTL_1H


def test_cache_atomic_write(tmp_path: Path) -> None:
    """Cache put must use atomic write (no partial files on interrupt)."""
    cache = HttpCache("atomic-test", base_dir=tmp_path)
    cache.put("key", {"data": "test"})

    entry_path = cache._entry_path("key")
    assert entry_path.is_file()
    data = json.loads(entry_path.read_text(encoding="utf-8"))
    assert data["value"] == {"data": "test"}
    assert "cached_at" in data
