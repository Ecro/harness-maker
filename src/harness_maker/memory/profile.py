"""Profile memory layer — cumulative user pattern tracking."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from harness_maker.memory._locking import exclusive_lock


class ProfileStore:
    """Tracks user behavior patterns and preferences across sessions.

    Stores key-value observations (e.g., preferred_style, common_errors,
    domain_expertise) that accumulate over time. Each key can have a
    history of values with timestamps for trend analysis.
    """

    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir / "profile"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._store_path = self._dir / "profile.json"
        self._lock_path = self._dir / "profile.lock"

    def get(self, key: str) -> Any:
        """Get the latest value for a profile key.

        0.7.1 (ADR-104): reads do NOT acquire the lock. POSIX ``os.replace``
        guarantees readers see either the old file or the new file in full,
        never a torn state — but a read concurrent with a write may return
        the pre-write snapshot.
        """
        data = self._read()
        entry = data.get(key)
        if entry is None:
            return None
        if isinstance(entry, dict) and "value" in entry:
            return entry["value"]
        return entry

    def set(self, key: str, value: Any, *, timestamp: str = "") -> None:
        """Set a profile key. Appends to history if key exists.

        Wraps the read-modify-write block in an exclusive POSIX flock so
        concurrent set() calls on different keys do not clobber each other
        (prior implementation silently lost the second writer's update).
        """
        with exclusive_lock(self._lock_path):
            data = self._read()
            existing = data.get(key)
            if isinstance(existing, dict) and "history" in existing:
                existing["history"].append(
                    {"value": existing["value"], "ts": existing.get("ts", "")}
                )
                existing["value"] = value
                existing["ts"] = timestamp
            else:
                data[key] = {"value": value, "ts": timestamp, "history": []}
            self._write(data)

    def get_all(self) -> dict[str, Any]:
        """Read the entire profile.

        0.7.1 (ADR-104): same lock-free read contract as ``get`` — readers
        see either old or new file fully (``os.replace`` atomicity), never
        torn. Strict-freshness callers must serialize externally.
        """
        return self._read()

    def _read(self) -> dict[str, Any]:
        if not self._store_path.is_file():
            return {}
        try:
            return json.loads(self._store_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, ValueError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        fd, tmp = tempfile.mkstemp(
            dir=str(self._store_path.parent),
            prefix=f".{self._store_path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, self._store_path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
