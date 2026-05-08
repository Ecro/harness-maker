"""Semantic memory layer — LLM-summarized knowledge with keyword index."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from harness_maker.memory._locking import exclusive_lock


class SemanticStore:
    """Structured knowledge store — summaries, patterns, conventions.

    Maps naturally to existing wiki.md / failures.md content. Each entry
    has a slug, category, summary, and keyword list for retrieval.
    """

    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir / "semantic"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.jsonl"
        self._lock_path = self._dir / "index.lock"

    def write(
        self,
        *,
        slug: str,
        category: str,
        summary: str,
        keywords: list[str],
        source: str = "",
    ) -> dict[str, Any]:
        """Write or update a semantic entry. Deduplicates by slug.

        Acquires an exclusive POSIX flock around the read-modify-replace
        block so two concurrent sessions writing different slugs cannot
        clobber each other (the prior implementation silently lost the
        second writer's update).
        """
        entry: dict[str, Any] = {
            "slug": slug,
            "category": category,
            "summary": summary,
            "keywords": keywords,
            "source": source,
        }
        with exclusive_lock(self._lock_path):
            existing = self._read_index()
            updated = [e for e in existing if e.get("slug") != slug]
            updated.append(entry)
            self._write_index(updated)
        return entry

    def read_all(self) -> list[dict[str, Any]]:
        """Read all semantic entries."""
        return self._read_index()

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search entries by keyword match (case-insensitive substring)."""
        q = query.lower()
        results: list[dict[str, Any]] = []
        for entry in self._read_index():
            keywords = entry.get("keywords", [])
            summary = entry.get("summary", "")
            slug = entry.get("slug", "")
            if any(q in kw.lower() for kw in keywords) or q in summary.lower() or q in slug.lower():
                results.append(entry)
        return results

    def _read_index(self) -> list[dict[str, Any]]:
        if not self._index_path.is_file():
            return []
        entries: list[dict[str, Any]] = []
        for line in self._index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
        return entries

    def _write_index(self, entries: list[dict[str, Any]]) -> None:
        content = "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n"
        fd, tmp = tempfile.mkstemp(
            dir=str(self._index_path.parent),
            prefix=f".{self._index_path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, self._index_path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
