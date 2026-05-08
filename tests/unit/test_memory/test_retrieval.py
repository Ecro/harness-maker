"""Tests for cross-layer memory retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from harness_maker.memory.retrieval import MemoryRetriever


def test_retrieve_semantic_only(tmp_path: Path) -> None:
    r = MemoryRetriever(tmp_path)
    r.semantic.write(
        slug="atomic-write",
        category="pattern",
        summary="Always use atomic_write",
        keywords=["atomic", "write"],
    )
    result = r.retrieve("atomic", include_episodic=False, include_profile=False)
    assert len(result["semantic"]) == 1
    assert "episodic" not in result
    assert "profile" not in result


def test_retrieve_all_layers(tmp_path: Path) -> None:
    r = MemoryRetriever(tmp_path)
    r.semantic.write(slug="s1", category="a", summary="test pattern", keywords=["test"])
    r.profile.set("style", "concise")
    ts = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)
    r.episodic.write(session_id="x", stage="test", payload={"test": True}, timestamp=ts)

    result = r.retrieve("test", episodic_date="2026-05-08")
    assert "semantic" in result
    assert "episodic" in result
    assert "profile" in result
    assert len(result["semantic"]) == 1
    assert len(result["episodic"]) >= 1


def test_retrieve_episodic_without_date(tmp_path: Path) -> None:
    r = MemoryRetriever(tmp_path)
    result = r.retrieve("anything")
    assert result["episodic"] == []


def test_write_retrieve_cycle(tmp_path: Path) -> None:
    """End-to-end: write to all layers, then retrieve and verify."""
    r = MemoryRetriever(tmp_path)
    ts = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)
    r.episodic.write(
        session_id="s1",
        stage="execute",
        payload={"file": "auth.py", "action": "refactor"},
        timestamp=ts,
    )
    r.semantic.write(
        slug="auth-refactor",
        category="pattern",
        summary="Auth module refactored to use token-based flow",
        keywords=["auth", "refactor", "token"],
    )
    r.profile.set("domain_expertise", ["auth", "security"])

    result = r.retrieve("auth", episodic_date="2026-05-08")
    assert len(result["semantic"]) == 1
    assert result["semantic"][0]["slug"] == "auth-refactor"
    assert len(result["episodic"]) >= 1
    assert result["profile"]["domain_expertise"]["value"] == ["auth", "security"]
