"""Hybrid telemetry hook — adapts to both Claude Code and Cursor IDE.

Per amendment §H. Hook input arrives via stdin as JSON; output is "ok" on stdout.
Must NEVER crash Claude Code or Cursor: malformed input → empty entry, exit 0.

Event shapes (PLAN-cursor-rootcause.md follow-up):

- **post_tool_use** (Claude Code PostToolUse): payload has `tool_name` + `usage`.
  We extract token counts for cache-diagnostic Layer 3.
- **stop** (Cursor stop): payload has `status` / `loop_count` / `duration_ms` but
  NO `usage` (Cursor does not surface tokens in any hook event — confirmed by
  Cursor team in <https://forum.cursor.com/t/cursordiskkv-table-records-always-show-0-for-tokencount/155984>).
  We capture per-turn signals; cache_diagnostics filters these out so they
  don't pollute hit-rate calculation.
- **unknown**: minimal entry (timestamp + event hint) — never silently skip.

Each entry carries an `event` field so downstream readers can filter cleanly.
Older entries (pre-0.5.4) lacked this field; cache_diagnostics treats absent
`event` as `post_tool_use` for backward compatibility.

Phase 9 (personalization-depth) adds the ``harness_yaml_override`` event type
recorded in a separate file ``.claude/observability/adaptive/overrides.jsonl``.
See ``OverrideRecord`` / ``emit_override`` / ``load_overrides`` /
``compute_yaml_diff`` below. ADR-005: 100% local; never opens a socket.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from harness_maker.io_utils import atomic_write

# Version of the `metrics-*.jsonl` ENTRY shape. Distinct from `SCHEMA_VERSION`, which
# versions OverrideRecord / `adaptive/overrides.jsonl` — bumping that one would make
# `_read_overrides` silently drop every existing override row.
# v2 (PLAN-harness-economics-observability ADR-005): the four token fields and
# `cost_usd` were removed. The Claude Code PostToolUse payload carries no `usage`, so
# they were structurally zero on every line ever written (0 non-zero in 2175 measured).
# ABSENT KEY => schema 1 (pre-retirement); readers must apply that default.
METRICS_SCHEMA_VERSION = 2

COST_PER_MTK: dict[str, dict[str, float]] = {
    "opus": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
    "sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
    "haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.025, "cache_write": 0.3},
}
_DEFAULT_COST = COST_PER_MTK["sonnet"]

# ADR-107 (0.7.1): persist only the tool_input keys that scan_sequence /
# prod_name_guard inspect. Foreign fields are dropped — minimises secret-
# leak surface and keeps the persisted line size bounded.
_ALLOWED_TOOL_INPUT_KEYS: frozenset[str] = frozenset(
    {"path", "file_path", "command", "target", "database", "url", "query"}
)
_VALUE_CAP = 256

# ADR-107 secret-pattern redaction. Applied per string value BEFORE the
# 256-char cap so a partial-token tail can never survive truncation.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),  # Anthropic / OpenAI keys
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub personal access tokens
    re.compile(r"AKIA[A-Z0-9]{16,}"),  # AWS access keys
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),  # OAuth Bearer
)


def _redact_value(s: str) -> str:
    """Apply known-secret-pattern redaction; keep value otherwise unchanged."""
    for pattern in _SECRET_PATTERNS:
        s = pattern.sub("[REDACTED]", s)
    return s


def _project_tool_input(raw: dict[str, Any]) -> dict[str, Any]:
    """Whitelist-project tool_input → safe, capped, secret-redacted dict.

    Prevents both schema bloat (foreign keys with potentially-sensitive
    values) and partial-secret leaks via end-of-buffer truncation. Each
    string value is redacted FIRST, then capped at 256 chars; non-string
    primitives (int/bool/null) pass through unchanged.
    """
    safe: dict[str, Any] = {}
    for key in _ALLOWED_TOOL_INPUT_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, str):
            redacted = _redact_value(value)
            if len(redacted) > _VALUE_CAP:
                redacted = redacted[:_VALUE_CAP] + "...<truncated>"
            safe[key] = redacted
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key] = value
        # Drop non-primitive nested values (lists/dicts) — scan_sequence
        # only consults primitive values via _extract_target.
    return safe


def _detect_event(data: dict[str, Any]) -> str:
    """Classify payload shape into a known event type.

    Order matters: tool_name is the strongest signal (post_tool_use carries
    it on both IDEs). status/loop_count are unique to Cursor's stop event.
    Anything else (e.g. session_start with no useful fields) → unknown.
    """
    if "tool_name" in data:
        return "post_tool_use"
    if "status" in data or "loop_count" in data or "duration_ms" in data:
        return "stop"
    return "unknown"


def _build_entry(data: dict[str, Any]) -> dict[str, Any]:
    """Adapt the stdin payload to a JSONL entry tagged by event type."""
    event = _detect_event(data)
    entry: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "span_id": uuid.uuid4().hex[:16],
        "trace_id": data.get("conversation_id") or uuid.uuid4().hex,
        "event": event,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
    }
    if event == "post_tool_use":
        entry["tool_name"] = data.get("tool_name")
        # 0.7.1 (ADR-107): whitelist-project tool_input → known-good keys
        # with value-level secret redaction + 256-char cap. Replaces the
        # earlier 2 KiB string-slice that produced invalid JSON on overflow
        # and could preserve partial-secret tails.
        raw_input = data.get("tool_input")
        if isinstance(raw_input, dict):
            safe_input = _project_tool_input(raw_input)
            if safe_input:
                # Persist as a JSON string so the on-disk schema stays
                # compatible with pre-0.7.1 consumers reading `tool_input`.
                entry["tool_input"] = json.dumps(safe_input, ensure_ascii=False)
    elif event == "stop":
        # Cursor stop fires once per agent turn — meaningful per-turn signal
        # even though tokens aren't available. status/loop_count/duration_ms
        # power custom dashboards; conversation_id allows cross-session join.
        entry["status"] = data.get("status")
        entry["loop_count"] = data.get("loop_count")
        entry["duration_ms"] = data.get("duration_ms")
        entry["model"] = data.get("model")
        entry["conversation_id"] = data.get("conversation_id")
    return entry


def main() -> int:
    raw = ""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        raw = ""
    data: dict[str, Any] = {}
    if raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                data = parsed
        except (json.JSONDecodeError, ValueError):
            data = {}
    raw_workspace = data.get("workspace")
    workspace: dict[str, Any] = raw_workspace if isinstance(raw_workspace, dict) else {}
    # Resolve project root via env-var-first chain (ADR-102, 0.7.1):
    #   1. CLAUDE_PROJECT_DIR — Claude Code-native, set per-session
    #   2. CURSOR_PROJECT_DIR — Cursor-native equivalent
    #   3. workspace.current_dir from stdin (Claude Code's typed payload —
    #      shape is well-defined, unlike the bare `cwd` key which a poisoned
    #      tool result could spoof)
    #   4. os.getcwd() — last-resort fallback; may be $HOME or / if the IDE
    #      spawns the hook from outside the project
    # The bare stdin `cwd` field is intentionally NOT consulted: prior to
    # 0.7.1 it was a path-traversal primitive (a poisoned PostToolUse
    # payload could redirect metrics writes to an attacker-chosen path).
    cwd_str = (
        os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CURSOR_PROJECT_DIR")
        or workspace.get("current_dir")
        or os.getcwd()
    )
    cwd = Path(cwd_str)
    # ADR-103 (0.7.1): rotate per-day so a long-lived session does not
    # accumulate an unbounded single file. Readers (security_scanner,
    # cache_diagnostics) walk dated files newest-first via _metrics_io
    # and fall back to the legacy `metrics.jsonl` for pre-0.7.1 entries.
    obs_dir = cwd / ".claude" / "observability"
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    metrics_path = obs_dir / f"metrics-{today}.jsonl"
    try:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        entry = _build_entry(data)
        # Atomic append: O_APPEND + a single os.write() syscall guarantees
        # POSIX atomicity for writes ≤ PIPE_BUF (4096 bytes). One JSONL entry
        # is ~200–400 bytes, well within the bound. The buffered TextIOWrapper
        # returned by ``Path.open("a")`` could split a write across multiple
        # syscalls and let two concurrent hooks interleave their lines; using
        # raw os.write() bypasses Python's buffer.
        line = (json.dumps(entry) + "\n").encode("utf-8")
        fd = os.open(
            str(metrics_path),
            os.O_WRONLY | os.O_APPEND | os.O_CREAT,
            0o644,
        )
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except OSError as e:
        print(f"telemetry write failed: {e}", file=sys.stderr)
        return 0  # Never block Claude Code
    print("ok")
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# Phase 9 — harness_yaml_override event capture (ADR-005 / Validator C3 / W8)
# ──────────────────────────────────────────────────────────────────────────────

HARNESS_YAML_OVERRIDE = "harness_yaml_override"
SCHEMA_VERSION = 1
"""Bump only on incompatible schema change. Phase 10 reader skips unknown
versions with a warning (validator C3)."""

OverrideSource = Literal["configure-exit", "session-start", "git-fallback"]


class OverrideRecord(BaseModel):
    """One axis-level edit to ``harness.yaml`` captured for B4 audit.

    Why pydantic + ``extra="forbid"``: a malformed jsonl line (e.g. an
    older schema_version with foreign fields) would otherwise propagate
    through Phase 10's audit reader as silently-typed dict noise. Forbid
    + filter-on-load gives Phase 10 a clean contract.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: int = SCHEMA_VERSION
    ts: str
    axis_path: str
    before: Any = None
    after: Any = None
    source: OverrideSource
    reason: str = ""


def _overrides_path(project_dir: Path) -> Path:
    """Resolve the on-disk jsonl path. Centralised so tests + emitters
    cannot diverge on the location."""
    return project_dir / ".claude" / "observability" / "adaptive" / "overrides.jsonl"


def _dedup_key(record: OverrideRecord) -> str:
    """Stable identity for a logical override event.

    Same ts + axis_path + after means the same user edit observed by the
    primary (configure-exit) and secondary (session-start) capture sites;
    we record it once. ``after`` uses ``repr`` so type information
    survives (``True`` vs ``"True"`` are distinct)."""
    return f"{record.ts}|{record.axis_path}|{record.after!r}"


def _load_existing_lines(path: Path) -> list[str]:
    """Read the existing jsonl as raw lines (preserves unknown-schema entries).

    We keep unknown-schema lines verbatim on round-trip because dropping
    them would silently lose data on a partial rollback. Filtering only
    happens on the typed load path."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


def _is_duplicate(record: OverrideRecord, existing_lines: list[str]) -> bool:
    """True when ``record`` matches the dedup key of any existing entry.

    Skips lines that fail to parse — corrupt lines do not block emission
    of new records (validator W8: dedup is best-effort, never gates write).
    """
    target_key = _dedup_key(record)
    for line in existing_lines:
        try:
            existing_data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(existing_data, dict):
            continue
        ts = existing_data.get("ts")
        axis = existing_data.get("axis_path")
        after = existing_data.get("after")
        if ts is None or axis is None:
            continue
        if f"{ts}|{axis}|{after!r}" == target_key:
            return True
    return False


def emit_override(
    record: OverrideRecord,
    project_dir: Path,
    *,
    disable_telemetry: bool = False,
) -> None:
    """Append ``record`` to ``overrides.jsonl`` unless telemetry is opted out.

    ADR-005: when ``disable_telemetry=True`` we short-circuit before any
    disk I/O so the opt-out is observable in tests via mock-fs and so a
    later audit reader does not see partial records.

    Idempotent: re-emitting the same logical event (matching dedup key)
    is a no-op — supports the dual-capture design (validator W8) where
    both /hm:configure-exit and SessionStart can observe one edit.
    """
    if disable_telemetry:
        return
    path = _overrides_path(project_dir)
    existing = _load_existing_lines(path)
    if _is_duplicate(record, existing):
        return
    new_line = record.model_dump_json()
    body = "\n".join(existing + [new_line]) + "\n"
    atomic_write(path, body)


def load_overrides(
    project_dir: Path,
    *,
    schema_version_filter: int = SCHEMA_VERSION,
) -> list[OverrideRecord]:
    """Read overrides.jsonl, returning only records matching the schema filter.

    Validator C3: a forward-compatible reader skips unknown schema_version
    entries with a stderr warning instead of crashing. Lines that fail to
    parse are skipped silently — telemetry must NEVER block the consumer.
    """
    path = _overrides_path(project_dir)
    if not path.is_file():
        return []
    out: list[OverrideRecord] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        version = data.get("schema_version")
        if version != schema_version_filter:
            print(
                f"telemetry: skipping override entry with schema_version={version!r} "
                f"(expected {schema_version_filter})",
                file=sys.stderr,
            )
            continue
        try:
            out.append(OverrideRecord.model_validate(data))
        except (ValueError, TypeError) as e:
            print(f"telemetry: malformed override entry skipped: {e}", file=sys.stderr)
            continue
    return out


def _walk_diff(
    before: Any,
    after: Any,
    *,
    prefix: str,
    ts: str,
    source: OverrideSource,
    out: list[OverrideRecord],
) -> None:
    """Recursive worker for ``compute_yaml_diff``.

    Only leaf-value differences produce records. Nested dicts are
    traversed deeper; for any branch where both sides are dicts we
    recurse so nested-leaf changes get their own dotted ``axis_path``.
    When the two sides have different structural shapes (one is dict,
    the other scalar/list), the whole subtree counts as one leaf change.
    """
    if isinstance(before, dict) and isinstance(after, dict):
        all_keys = set(before.keys()) | set(after.keys())
        for key in sorted(all_keys):
            if isinstance(key, str) and key.startswith("_"):
                continue
            sub_prefix = f"{prefix}.{key}" if prefix else str(key)
            _walk_diff(
                before.get(key),
                after.get(key),
                prefix=sub_prefix,
                ts=ts,
                source=source,
                out=out,
            )
        return
    if before == after:
        return
    out.append(
        OverrideRecord(
            ts=ts,
            axis_path=prefix,
            before=before,
            after=after,
            source=source,
        )
    )


def compute_yaml_diff(
    before_yaml: dict[str, Any],
    after_yaml: dict[str, Any],
    ts: str,
    *,
    source: OverrideSource = "configure-exit",
) -> list[OverrideRecord]:
    """Diff two yaml-loaded dicts, producing one OverrideRecord per leaf change.

    Why dotted axis_path: the Phase 10 audit groups by axis_path for the
    L2 (override stability) score, so a stable string key is the contract.

    Keys starting with ``_`` are skipped — those are reserved for private
    telemetry breadcrumbs (e.g. a future ``_render_provenance``) that
    must not show up as user-driven overrides.
    """
    out: list[OverrideRecord] = []
    _walk_diff(before_yaml, after_yaml, prefix="", ts=ts, source=source, out=out)
    return out


def now_iso() -> str:
    """ISO 8601 UTC timestamp matching the existing metrics line schema."""
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
