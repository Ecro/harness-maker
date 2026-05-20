"""BatchSpecState — CRUD helper for prompt-driven /hm:loop p5-batch-N (ADR-013 R2).

This is **not** an `autoloop_driver.ExecutorCallable`. It is a thin
state-tracker over ``work-docs/p5-batch-state.yaml``: the prompt-side
batch procedure reads next_batch_queue(), invokes /hm:spec for each
feature, then calls mark_complete(). Pure file CRUD via atomic_write.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from harness_maker.io_utils import atomic_write

BatchSpecStatus = Literal["queued", "in_progress", "complete", "failed"]


class BatchEntry(BaseModel):
    feature_id: str
    parent_spec_slug: str | None = None
    status: BatchSpecStatus = "queued"
    last_attempt: str | None = None
    note: str = ""


class BatchSpecStateModel(BaseModel):
    """Persisted shape on disk."""

    schema_version: int = 1
    batch_number: int
    entries: list[BatchEntry] = Field(default_factory=list)


class BatchSpecState:
    """In-memory + on-disk batch-progress CRUD.

    Constructor reads existing yaml at ``state_path`` or seeds an empty
    one. All mutation methods persist via ``atomic_write``.
    """

    def __init__(self, state_path: Path, *, batch_number: int = 0) -> None:
        self._path = state_path
        if state_path.exists():
            data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
            self._model = BatchSpecStateModel.model_validate(data)
        else:
            self._model = BatchSpecStateModel(batch_number=batch_number)

    # ---- public API ----------------------------------------------------

    @property
    def batch_number(self) -> int:
        return self._model.batch_number

    def next_batch_queue(self, limit: int | None = None) -> list[BatchEntry]:
        """Return the queued entries (oldest first) up to ``limit``."""
        queued = [e for e in self._model.entries if e.status == "queued"]
        return queued if limit is None else queued[:limit]

    def add_features(self, feature_ids: list[str]) -> None:
        existing = {e.feature_id for e in self._model.entries}
        for fid in feature_ids:
            if fid in existing:
                continue
            self._model.entries.append(BatchEntry(feature_id=fid))
        self._persist()

    def mark_in_progress(self, feature_id: str, *, at_iso: str | None = None) -> None:
        entry = self._find(feature_id)
        entry.status = "in_progress"
        if at_iso is not None:
            entry.last_attempt = at_iso
        self._persist()

    def mark_complete(
        self,
        feature_id: str,
        *,
        at_iso: str | None = None,
        note: str = "",
    ) -> None:
        entry = self._find(feature_id)
        entry.status = "complete"
        if at_iso is not None:
            entry.last_attempt = at_iso
        if note:
            entry.note = note
        self._persist()

    def mark_failed(
        self,
        feature_id: str,
        *,
        at_iso: str | None = None,
        note: str = "",
    ) -> None:
        entry = self._find(feature_id)
        entry.status = "failed"
        if at_iso is not None:
            entry.last_attempt = at_iso
        if note:
            entry.note = note
        self._persist()

    def current_progress(self) -> dict[str, int]:
        """Return counts per status (used in loop progress prints)."""
        counts: dict[str, int] = {
            "queued": 0,
            "in_progress": 0,
            "complete": 0,
            "failed": 0,
        }
        for e in self._model.entries:
            counts[e.status] = counts.get(e.status, 0) + 1
        return counts

    # ---- internals -----------------------------------------------------

    def _find(self, feature_id: str) -> BatchEntry:
        for e in self._model.entries:
            if e.feature_id == feature_id:
                return e
        raise KeyError(f"feature_id not in batch: {feature_id!r}")

    def _persist(self) -> None:
        payload = self._model.model_dump(mode="json")
        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        atomic_write(self._path, text)


__all__ = [
    "BatchEntry",
    "BatchSpecState",
    "BatchSpecStateModel",
    "BatchSpecStatus",
]
