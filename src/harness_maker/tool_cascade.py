"""Tool cascade firewall — recovery taxonomy for tool failures (Phase 7).

Implements retry → switch → abort cascade when tools fail. Each failure is
logged to JSONL for observability. No chaos test (deferred to 0.8.0).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path


class RecoveryAction(str, Enum):  # noqa: UP042
    RETRY = "retry"
    SWITCH = "switch"
    ABORT = "abort"


class ToolCascade:
    """Manages tool failure recovery with configurable cascade policy."""

    def __init__(
        self,
        *,
        max_retries: int = 3,
        alternatives: dict[str, list[str]] | None = None,
        log_path: Path | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._alternatives = alternatives or {}
        self._log_path = log_path
        self._failure_counts: dict[str, int] = {}
        self._switch_history: dict[str, list[str]] = {}

    def on_failure(
        self,
        tool_name: str,
        error: str,
    ) -> tuple[RecoveryAction, str]:
        """Decide recovery action for a tool failure.

        Returns (action, target) where:
        - RETRY: target = same tool_name
        - SWITCH: target = alternative tool name
        - ABORT: target = ""
        """
        count = self._failure_counts.get(tool_name, 0) + 1
        self._failure_counts[tool_name] = count

        self._log_failure(tool_name, error, count)

        if count <= self._max_retries:
            return RecoveryAction.RETRY, tool_name

        alts = self._alternatives.get(tool_name, [])
        tried = self._switch_history.get(tool_name, [])
        for alt in alts:
            if alt not in tried:
                self._switch_history.setdefault(tool_name, []).append(alt)
                return RecoveryAction.SWITCH, alt

        return RecoveryAction.ABORT, ""

    def reset(self, tool_name: str) -> None:
        """Reset failure count on success."""
        self._failure_counts.pop(tool_name, None)

    def get_failure_count(self, tool_name: str) -> int:
        return self._failure_counts.get(tool_name, 0)

    def _log_failure(self, tool_name: str, error: str, count: int) -> None:
        if self._log_path is None:
            return
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "tool_name": tool_name,
            "error": error,
            "failure_count": count,
        }
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._log_path.parent),
            prefix=f".{self._log_path.name}.",
            suffix=".tmp",
        )
        try:
            existing = ""
            if self._log_path.exists():
                existing = self._log_path.read_text(encoding="utf-8")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(existing + json.dumps(entry, ensure_ascii=False) + "\n")
            os.replace(tmp, self._log_path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
