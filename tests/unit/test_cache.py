"""Tests for cache.HttpCache — mutation-killing suite (P0.5 follow-up).

The first 8 tests are the original smoke suite from prior P0.5 commit.
The remaining 16 target the specific mutants identified by the initial mutmut
baseline (kill rate ~4%) to lift the score above the T2 floor (70%).
Each test below names the mutant id(s) it intends to kill in its docstring.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from harness_maker.cache import HttpCache, _cache_base


# ---------------------------------------------------------------------------
# Original smoke tests (kept for backward compat)
# ---------------------------------------------------------------------------


def test_cache_base_default_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARNESS_MAKER_CACHE_DIR", raising=False)
    base = _cache_base()
    assert str(base).endswith(".cache/harness-maker")


def test_cache_base_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HARNESS_MAKER_CACHE_DIR", str(tmp_path / "override"))
    assert _cache_base() == tmp_path / "override"


def test_get_miss_returns_none(tmp_path: Path) -> None:
    cache = HttpCache("test_src", base_dir=tmp_path)
    assert cache.get("nope", ttl=60) is None


def test_get_or_fetch_invokes_fetcher_on_miss(tmp_path: Path) -> None:
    cache = HttpCache("test_src", base_dir=tmp_path)
    calls = {"n": 0}

    def fetcher() -> dict[str, int]:
        calls["n"] += 1
        return {"v": 42}

    out = cache.get_or_fetch("k1", fetcher, ttl=60)
    assert out == {"v": 42}
    assert calls["n"] == 1


def test_get_or_fetch_uses_cache_on_hit(tmp_path: Path) -> None:
    cache = HttpCache("test_src", base_dir=tmp_path)
    calls = {"n": 0}

    def fetcher() -> dict[str, int]:
        calls["n"] += 1
        return {"v": 7}

    cache.get_or_fetch("k", fetcher, ttl=60)
    cache.get_or_fetch("k", fetcher, ttl=60)
    cache.get_or_fetch("k", fetcher, ttl=60)
    assert calls["n"] == 1


def test_entry_path_sanitizes_key(tmp_path: Path) -> None:
    cache = HttpCache("test_src", base_dir=tmp_path)
    p = cache._entry_path("a/b\\c")
    assert "/" not in p.name
    assert "\\" not in p.name


def test_cache_round_trip_via_disk(tmp_path: Path) -> None:
    cache = HttpCache("test_src", base_dir=tmp_path)

    def fetcher() -> list[int]:
        return [1, 2, 3]

    cache.get_or_fetch("k", fetcher, ttl=60)
    # New instance same dir should hit cache.
    cache2 = HttpCache("test_src", base_dir=tmp_path)
    calls = {"n": 0}

    def fetcher2() -> list[int]:
        calls["n"] += 1
        return [9, 9, 9]

    out = cache2.get_or_fetch("k", fetcher2, ttl=60)
    assert out == [1, 2, 3]
    assert calls["n"] == 0


def test_cache_corruption_falls_through_to_fetcher(tmp_path: Path) -> None:
    cache = HttpCache("test_src", base_dir=tmp_path)
    # Corrupt the cache file.
    p = cache._entry_path("k")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not valid json")

    def fetcher() -> str:
        return "fresh"

    out = cache.get_or_fetch("k", fetcher, ttl=60)
    assert out == "fresh"


# ---------------------------------------------------------------------------
# Mutation-killing tests
# ---------------------------------------------------------------------------


def test_typevar_t_name() -> None:  # noqa: N802 — kills mutants targeting TypeVar("T")
    """Kills mutants 1, 2 — TypeVar("T") name / None."""
    from harness_maker.cache import T

    assert T.__name__ == "T"


def test_constructor_creates_nested_base_dir(tmp_path: Path) -> None:
    """Kills mutant 12 — mkdir(parents=True) must propagate."""
    nested = tmp_path / "a" / "b" / "c"
    HttpCache("src", base_dir=nested)
    assert (nested / "src").is_dir()


def test_entry_path_replaces_forward_slash(tmp_path: Path) -> None:
    """Kills mutant 14 — key.replace("/", "_")."""
    cache = HttpCache("src", base_dir=tmp_path)
    p = cache._entry_path("path/with/slashes")
    assert "/" not in p.name
    assert p.name == "path_with_slashes.json"


def test_entry_path_replaces_backslash(tmp_path: Path) -> None:
    """Kills mutant 17 — key.replace("\\\\", "_")."""
    cache = HttpCache("src", base_dir=tmp_path)
    p = cache._entry_path("path\\with\\backslashes")
    assert "\\" not in p.name
    assert p.name == "path_with_backslashes.json"


def test_entry_path_both_separators(tmp_path: Path) -> None:
    """Kills mutant 18 — safe_key=None would TypeError, plus mutant 20 (f-string)."""
    cache = HttpCache("src", base_dir=tmp_path)
    p = cache._entry_path("a/b\\c")
    assert p.name == "a_b_c.json"
    assert p.suffix == ".json"


def test_get_treats_missing_cached_at_as_ancient(tmp_path: Path) -> None:
    """Kills mutant 26 — data.get("cached_at", 0) default must be 0 (not 1)."""
    cache = HttpCache("src", base_dir=tmp_path)
    cache._base.mkdir(parents=True, exist_ok=True)
    p = cache._entry_path("k")
    # Write entry WITHOUT cached_at — get() treats absence as ancient (0).
    p.write_text(json.dumps({"value": "v"}))
    # tiny ttl + default=0 → time.time() - 0 > 10 → True → expired
    assert cache.get("k", ttl=10) is None


def test_get_hit_with_explicit_cached_at(tmp_path: Path) -> None:
    """Kills mutant 27 — cached_at=None would crash; mutant 28 — sign flip."""
    cache = HttpCache("src", base_dir=tmp_path)
    cache._base.mkdir(parents=True, exist_ok=True)
    p = cache._entry_path("k")
    p.write_text(json.dumps({"cached_at": time.time(), "value": "v"}))
    assert cache.get("k", ttl=60) == "v"


def test_get_ttl_boundary_strict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kills mutant 29 — `> ttl` vs `>= ttl` boundary at elapsed==ttl."""
    cache = HttpCache("src", base_dir=tmp_path)
    # Pin time so cached_at is deterministic
    cached_at = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: cached_at)
    cache.put("k", "v")

    # Move clock forward to EXACTLY ttl seconds later.
    monkeypatch.setattr(time, "time", lambda: cached_at + 60.0)
    # `elapsed (60) > ttl (60)` is FALSE → still a hit. Mutant `>=` would miss.
    assert cache.get("k", ttl=60.0) == "v"

    # Move clock past ttl.
    monkeypatch.setattr(time, "time", lambda: cached_at + 60.001)
    assert cache.get("k", ttl=60.0) is None


def test_put_preserves_unicode(tmp_path: Path) -> None:
    """Kills mutant 35 — ensure_ascii=False keeps non-ASCII as literal UTF-8."""
    cache = HttpCache("src", base_dir=tmp_path)
    val = {"name": "한글-emoji-🎉", "list": ["α", "β", "γ"]}
    cache.put("k", val)
    # Inspect the raw file — non-ASCII bytes must survive (no \uXXXX escapes).
    raw = cache._entry_path("k").read_text(encoding="utf-8")
    assert "한글" in raw
    assert "🎉" in raw
    assert "α" in raw
    # Round-trip should restore the value verbatim.
    assert cache.get("k", ttl=60) == val


def test_invalidate_removes_existing_entry(tmp_path: Path) -> None:
    """Kills mutant 42 — path=None in invalidate would AttributeError."""
    cache = HttpCache("src", base_dir=tmp_path)
    cache.put("k", "v")
    p = cache._entry_path("k")
    assert p.is_file()
    cache.invalidate("k")
    assert not p.is_file()


def test_invalidate_nonexistent_does_not_raise(tmp_path: Path) -> None:
    """Kills mutant 43 — missing_ok=False would raise FileNotFoundError."""
    cache = HttpCache("src", base_dir=tmp_path)
    # No put — entry never exists. invalidate must be a no-op.
    cache.invalidate("never_existed")


def test_ttl_constants_exact_values() -> None:
    """Kills mutants 44, 45, 46, 47 — TTL_1H / TTL_24H must be exact."""
    from harness_maker.cache import TTL_1H, TTL_24H

    assert TTL_1H == 3600.0
    assert TTL_24H == 86400.0
    assert TTL_24H == TTL_1H * 24


def test_source_ttls_full_dict() -> None:
    """Kills mutants 48, 49, 50, 51, 52 — SOURCE_TTLS exact keys + values + non-null."""
    from harness_maker.cache import SOURCE_TTLS, TTL_1H, TTL_24H

    assert SOURCE_TTLS is not None
    assert SOURCE_TTLS == {
        "anthropic_blog": TTL_24H,
        "github_releases": TTL_1H,
        "arxiv": TTL_24H,
        "osv_dev": TTL_1H,
    }
    # Key set is exactly these four — string mutations are detected.
    assert set(SOURCE_TTLS.keys()) == {"anthropic_blog", "github_releases", "arxiv", "osv_dev"}
    # Value set narrows to the two constants.
    assert set(SOURCE_TTLS.values()) == {TTL_1H, TTL_24H}


def test_put_then_get_explicit_value_type(tmp_path: Path) -> None:
    """Kills mutant 40 — cast("T", cached) string mutation (best-effort).

    cast() is a type-only no-op at runtime, so direct kill is hard. We verify
    that the value type is preserved through cache round-trip via
    get_or_fetch's typed-return path.
    """
    cache = HttpCache("src", base_dir=tmp_path)
    cache.put("k", {"nested": [1, 2, 3]})
    out = cache.get_or_fetch("k", lambda: {"new": [9, 9]}, ttl=60)
    # First call must hit cache; if cast were broken the return path could
    # be wrong but runtime cast is identity.
    assert out == {"nested": [1, 2, 3]}


def test_get_invalid_json_returns_none(tmp_path: Path) -> None:
    """Direct test for the json.JSONDecodeError branch (defensive)."""
    cache = HttpCache("src", base_dir=tmp_path)
    cache._base.mkdir(parents=True, exist_ok=True)
    p = cache._entry_path("k")
    p.write_text("{ garbage ")
    assert cache.get("k", ttl=60) is None


def test_get_or_fetch_persists_after_miss(tmp_path: Path) -> None:
    """Verify fetcher result is actually persisted (kills surviving 'no-write' mutants)."""
    cache = HttpCache("src", base_dir=tmp_path)
    cache.get_or_fetch("k", lambda: "fresh", ttl=60)
    assert cache._entry_path("k").is_file()
    # File contents must be the fetcher's value.
    raw = cache._entry_path("k").read_text(encoding="utf-8")
    assert "fresh" in raw
