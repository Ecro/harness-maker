"""Tests for semantic memory layer."""

from __future__ import annotations

from pathlib import Path

from harness_maker.memory.semantic import SemanticStore


def test_write_and_read(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    entry = store.write(
        slug="atomic-write",
        category="pattern",
        summary="Always use atomic_write for disk persistence",
        keywords=["file", "write", "atomic"],
    )
    assert entry["slug"] == "atomic-write"
    all_entries = store.read_all()
    assert len(all_entries) == 1


def test_deduplicates_by_slug(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    store.write(slug="x", category="a", summary="v1", keywords=["k1"])
    store.write(slug="x", category="a", summary="v2", keywords=["k2"])
    all_entries = store.read_all()
    assert len(all_entries) == 1
    assert all_entries[0]["summary"] == "v2"


def test_search_by_keyword(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    store.write(slug="auth", category="pattern", summary="Auth flow", keywords=["auth", "security"])
    store.write(slug="perf", category="pattern", summary="Perf tips", keywords=["performance"])
    results = store.search("auth")
    assert len(results) == 1
    assert results[0]["slug"] == "auth"


def test_search_by_summary(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    store.write(slug="x", category="a", summary="Use atomic_write everywhere", keywords=[])
    results = store.search("atomic")
    assert len(results) == 1


def test_search_case_insensitive(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    store.write(slug="x", category="a", summary="Test", keywords=["PyTest"])
    results = store.search("pytest")
    assert len(results) == 1


def test_empty_store_search(tmp_path: Path) -> None:
    store = SemanticStore(tmp_path)
    assert store.search("anything") == []
