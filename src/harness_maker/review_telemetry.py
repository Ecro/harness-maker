"""Per-`/hm:review` telemetry emitter — append-only JSONL.

PLAN-llm-code-review-2026 ADR-006 specifies a per-session JSONL line keyed
to `.claude/observability/review-{YYYY-MM-DD}.jsonl`. Append uses POSIX
`O_APPEND` so writes ≤ PIPE_BUF (4096 bytes) are kernel-atomic — sufficient
for the 14-field record. Concurrent reviewers (autoloop + Cursor sharing
``.worktrees/``) thereby serialize at the kernel level without explicit
locking.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Default location relative to project root — overridable via parameter.
DEFAULT_OBSERVABILITY_DIR = Path(".claude/observability")


class ReviewTelemetryRecord(BaseModel):
    """One row appended per `/hm:review` invocation.

    Numeric fields default to 0 (not None) so downstream aggregations can sum
    without null-coalescing. ``fixture_label`` and the two ``verifier_false_*``
    counts are null on real runs (only labeled-fixture runs compute them).
    ``fallback`` is set only when the verifier model was unavailable.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    # max_length on string fields guards the PIPE_BUF (4096-byte) atomic
    # append at the schema layer, so callers get a clear validation error
    # instead of a confusing late-write ValueError (security-reviewer P2).
    ts: str = Field(max_length=64)
    slug: str = Field(max_length=200)
    round: int = Field(ge=1)
    pass1_n: int = Field(ge=0)
    verifier_kept_n: int = Field(ge=0)
    verifier_dropped_n: int = Field(ge=0)
    verifier_false_drop_n: int | None = None
    verifier_false_keep_n: int | None = None
    fixture_label: str | None = Field(default=None, max_length=200)
    pass2_kept_n: int = Field(ge=0)
    consensus_passed_n: int = Field(ge=0)
    wall_time_ms: int = Field(ge=0)
    build_break_count: int = Field(ge=0)
    auto_fix_reverted_n: int = Field(ge=0)
    fallback: str | None = Field(default=None, max_length=64)


def _utc_now_iso() -> str:
    """ISO 8601 second-resolution UTC stamp — deterministic for test override."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_log_path(observability_dir: Path) -> Path:
    return observability_dir / f"review-{datetime.now(tz=UTC).strftime('%Y-%m-%d')}.jsonl"


def _append_atomic_line(path: Path, line: str) -> None:
    """Append a single line via O_APPEND — kernel-atomic for writes ≤ PIPE_BUF.

    Raises if the line plus trailing newline would exceed 4096 bytes; callers
    must trim oversized fields rather than risk interleaving.

    Loops os.write to handle EINTR / signal-induced short writes — without
    the loop a truncated JSONL line could be fsync'd permanently
    (code-reviewer P1 finding).
    """
    payload = line if line.endswith("\n") else line + "\n"
    encoded = payload.encode("utf-8")
    if len(encoded) > 4096:
        raise ValueError(
            f"telemetry line {len(encoded)} bytes exceeds PIPE_BUF (4096); "
            "trim field content to preserve append atomicity"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(
        str(path),
        os.O_WRONLY | os.O_APPEND | os.O_CREAT,
        0o644,
    )
    try:
        view = memoryview(encoded)
        written = 0
        while written < len(view):
            n = os.write(fd, view[written:])
            if n == 0:
                # POSIX permits 0 only on certain non-blocking paths; for a
                # regular file with O_APPEND this would indicate a kernel
                # bug or disk-full edge case. Fail loud rather than spin.
                raise OSError("os.write returned 0 on telemetry append")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)


def emit(
    record: ReviewTelemetryRecord,
    *,
    project_root: Path | None = None,
    observability_dir: Path | None = None,
) -> Path:
    """Append one record. Returns the path written.

    ``project_root`` is prepended to ``observability_dir`` when both are
    relative; pass ``project_root=Path.cwd()`` from CLI sites. ``observability_dir``
    defaults to ``DEFAULT_OBSERVABILITY_DIR``.

    ``project_root`` is resolved before joining so traversal segments like
    ``..`` collapse into a concrete absolute path; callers that pass a
    deliberately relative path get the resolved equivalent for the same
    write target (security-reviewer P2 — emit hardening).

    When ``observability_dir`` is an absolute path AND ``project_root`` is
    set, the resolved absolute path must be contained within
    ``project_root.resolve()``; otherwise ``ValueError`` is raised. This
    prevents internal callers from accidentally (or via attacker-influenced
    config) writing JSONL outside the project tree
    (release-0-10-0 REVIEW O2 — absolute-path containment).
    """
    base_dir = observability_dir or DEFAULT_OBSERVABILITY_DIR
    if project_root:
        resolved_root = project_root.resolve()
        if base_dir.is_absolute():
            resolved_base = base_dir.resolve()
            if not resolved_base.is_relative_to(resolved_root):
                raise ValueError(
                    f"observability_dir {resolved_base} escapes project_root {resolved_root}"
                )
            base_dir = resolved_base
        else:
            base_dir = resolved_root / base_dir
    path = _today_log_path(base_dir)
    line = json.dumps(record.model_dump(), ensure_ascii=False, sort_keys=True)
    _append_atomic_line(path, line)
    return path


def record_from_dict(
    data: dict[str, Any],
    *,
    auto_timestamp: bool = True,
) -> ReviewTelemetryRecord:
    """Validate a raw dict against the telemetry schema.

    When ``auto_timestamp`` is true (default) and ``ts`` is missing, fills it
    with the current UTC instant — convenience for CLI callers that don't
    want to stamp every record themselves.
    """
    if auto_timestamp and "ts" not in data:
        data = {**data, "ts": _utc_now_iso()}
    return ReviewTelemetryRecord.model_validate(data)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m harness_maker.review_telemetry emit``.

    Reads a JSON object from stdin, validates, appends to today's JSONL.
    Writes the resolved log path to stdout on success.
    """
    args = list(sys.argv[1:]) if argv is None else list(argv)
    if not args or args[0] != "emit":
        sys.stderr.write("usage: python -m harness_maker.review_telemetry emit\n")
        return 2
    raw = sys.stdin.read()
    if not raw.strip():
        sys.stderr.write("emit: stdin is empty / invalid\n")
        return 1
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"emit: stdin is not valid JSON: {exc}\n")
        return 1
    if not isinstance(data, dict):
        sys.stderr.write("emit: stdin must decode to a JSON object\n")
        return 1
    try:
        record = record_from_dict(data)
    except ValidationError as exc:
        sys.stderr.write(f"emit: schema validation failed: {exc}\n")
        return 1
    path = emit(record, project_root=Path.cwd())
    sys.stdout.write(str(path) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
