"""Cross-layer memory retrieval with neighbor expansion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness_maker.memory.episodic import EpisodicStore
from harness_maker.memory.profile import ProfileStore
from harness_maker.memory.semantic import SemanticStore


class MemoryRetriever:
    """Unified retrieval across all 3 memory layers."""

    def __init__(self, base_dir: Path) -> None:
        self.episodic = EpisodicStore(base_dir)
        self.semantic = SemanticStore(base_dir)
        self.profile = ProfileStore(base_dir)

    def retrieve(
        self,
        query: str,
        *,
        include_episodic: bool = True,
        include_semantic: bool = True,
        include_profile: bool = True,
        episodic_date: str = "",
        episodic_limit: int = 10,
    ) -> dict[str, Any]:
        """Retrieve relevant context from all layers."""
        result: dict[str, Any] = {}

        if include_semantic:
            result["semantic"] = self.semantic.search(query)

        if include_episodic and episodic_date:
            events = self.episodic.read(episodic_date)
            q_lower = query.lower()
            matching: list[dict[str, Any]] = []
            for i, evt in enumerate(events):
                evt_str = str(evt).lower()
                if q_lower in evt_str:
                    neighbors = self.episodic.retrieve_neighbors(episodic_date, i, window=2)
                    matching.extend(neighbors)
            seen: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for m in matching:
                key = m.get("timestamp", "") + m.get("stage", "")
                if key not in seen:
                    seen.add(key)
                    deduped.append(m)
            result["episodic"] = deduped[:episodic_limit]
        elif include_episodic:
            result["episodic"] = []

        if include_profile:
            result["profile"] = self.profile.get_all()

        return result
