"""Tests for profile memory layer."""

from __future__ import annotations

from pathlib import Path

from harness_maker.memory.profile import ProfileStore


def test_set_and_get(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    store.set("preferred_style", "concise")
    assert store.get("preferred_style") == "concise"


def test_get_nonexistent_returns_none(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    assert store.get("missing") is None


def test_set_overwrites_with_history(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    store.set("style", "verbose", timestamp="t1")
    store.set("style", "concise", timestamp="t2")
    assert store.get("style") == "concise"
    data = store.get_all()
    assert len(data["style"]["history"]) == 1
    assert data["style"]["history"][0]["value"] == "verbose"


def test_get_all(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    store.set("a", 1)
    store.set("b", 2)
    data = store.get_all()
    assert "a" in data
    assert "b" in data


def test_empty_store(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    assert store.get_all() == {}
