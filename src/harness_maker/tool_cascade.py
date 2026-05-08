"""Tool cascade firewall — recovery taxonomy for tool failures (Phase 7).

Implements retry → switch → abort cascade when tools fail. Each failure is
logged to JSONL for observability. No chaos test (deferred to 0.8.0).
"""

from __future__ import annotations

import json
import os
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
        """Append a failure entry to the JSONL log.

        Uses POSIX ``O_APPEND`` + ``os.write`` so the syscall is atomic
        when the encoded line ≤ ``PIPE_BUF`` (4 KiB on Linux). Round-2
        Conc F2: errors with long stack traces can exceed PIPE_BUF; the
        encoded line is truncated to a safe boundary so the atomicity
        guarantee holds even on retry storms with verbose errors.
        """
        if self._log_path is None:
            return
        # Cap the error string so the entire encoded line stays under
        # PIPE_BUF and the os.write below remains a single atomic syscall.
        # Tracebacks beyond the cap are truncated; full context lives in
        # the original tool output, not here.
        capped_error = error if len(error) <= 1024 else error[:1024] + "...<truncated>"
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "tool_name": tool_name,
            "error": capped_error,
            "failure_count": count,
        }
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(str(self._log_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)
