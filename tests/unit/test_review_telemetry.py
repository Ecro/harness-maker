"""Phase A4 — review telemetry emitter unit tests.

ADR-006 contract:
- 14 fields (3 nullable, 1 fallback marker).
- Append-only JSONL via O_APPEND for kernel-atomic line writes.
- Concurrent reviewers (autoloop + Cursor) must not interleave lines.
- Daily-rotated file path under .claude/observability/review-{YYYY-MM-DD}.jsonl.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker.review_telemetry import (
    DEFAULT_OBSERVABILITY_DIR,
    ReviewTelemetryRecord,
    emit,
    record_from_dict,
)

_BASE_FIELDS = {
    "ts": "2026-05-11T12:00:00Z",
    "slug": "llm-code-review-2026",
    "round": 1,
    "pass1_n": 12,
    "verifier_kept_n": 9,
    "verifier_dropped_n": 3,
    "pass2_kept_n": 7,
    "consensus_passed_n": 5,
    "wall_time_ms": 18432,
    "build_break_count": 0,
    "auto_fix_reverted_n": 0,
}


def test_record_validates_required_fields() -> None:
    rec = ReviewTelemetryRecord(**_BASE_FIELDS)
    assert rec.slug == "llm-code-review-2026"
    assert rec.verifier_false_drop_n is None
    assert rec.fallback is None


def test_record_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        ReviewTelemetryRecord(**{**_BASE_FIELDS, "pass1_n": -1})


def test_record_rejects_unknown_field() -> None:
    """Strict + extra=forbid prevents silent telemetry-schema drift."""
    with pytest.raises(ValidationError):
        ReviewTelemetryRecord(**{**_BASE_FIELDS, "uncharted_field": "x"})


def test_record_from_dict_auto_stamps_ts() -> None:
    data = {k: v for k, v in _BASE_FIELDS.items() if k != "ts"}
    rec = record_from_dict(data)
    # Auto-stamp must match the ISO-second pattern from the module.
    parsed = datetime.strptime(rec.ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    delta = abs((datetime.now(tz=UTC) - parsed).total_seconds())
    assert delta < 5, f"auto-timestamp drifted by {delta}s"


def test_emit_writes_to_daily_file(tmp_path: Path) -> None:
    """emit() resolves to .claude/observability/review-{YYYY-MM-DD}.jsonl."""
    rec = ReviewTelemetryRecord(**_BASE_FIELDS)
    path = emit(rec, project_root=tmp_path)

    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    assert path == tmp_path / DEFAULT_OBSERVABILITY_DIR / f"review-{today}.jsonl"
    assert path.is_file()

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    for key, val in _BASE_FIELDS.items():
        assert parsed[key] == val


def test_emit_appends_subsequent_writes(tmp_path: Path) -> None:
    rec1 = ReviewTelemetryRecord(**_BASE_FIELDS)
    rec2 = ReviewTelemetryRecord(**{**_BASE_FIELDS, "round": 2, "wall_time_ms": 5000})
    p1 = emit(rec1, project_root=tmp_path)
    p2 = emit(rec2, project_root=tmp_path)
    assert p1 == p2  # same daily file
    lines = p1.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["round"] == 1
    assert json.loads(lines[1])["round"] == 2


def test_emit_concurrent_writers_no_interleave(tmp_path: Path) -> None:
    """Two threads writing simultaneously must produce 2 well-formed JSON lines.

    Guards risk #10 in PLAN-llm-code-review-2026: concurrent /hm:review
    sessions (autoloop + Cursor) sharing .claude/observability/.
    """
    n_per_thread = 25
    threads_n = 4

    def writer(thread_id: int) -> None:
        for i in range(n_per_thread):
            rec = ReviewTelemetryRecord(
                **{**_BASE_FIELDS, "slug": f"t{thread_id}-{i}", "round": (i % 9) + 1}
            )
            emit(rec, project_root=tmp_path)

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(threads_n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    path = tmp_path / DEFAULT_OBSERVABILITY_DIR / f"review-{today}.jsonl"
    lines = path.read_text().splitlines()
    assert len(lines) == n_per_thread * threads_n, (
        f"expected {n_per_thread * threads_n} lines, got {len(lines)}"
    )
    # Every line must be parseable JSON AND its re-serialized form must
    # equal the original line bytes — concurrency-reviewer P1: the prior
    # assertion (parseable + distinct slugs) would pass even if bytes
    # tore between threads, because interleaved fields could still
    # accidentally form valid JSON. Round-trip equivalence detects
    # any byte-level interleaving directly.
    slugs_seen = set()
    for line in lines:
        parsed = json.loads(line)
        round_tripped = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        assert round_tripped == line, (
            f"line bytes diverge from re-serialized JSON (tearing suspected):\n"
            f"  raw:        {line!r}\n  round-trip: {round_tripped!r}"
        )
        slugs_seen.add(parsed["slug"])
    assert len(slugs_seen) == n_per_thread * threads_n


def test_emit_oversized_slug_rejected_at_schema_layer() -> None:
    """Oversized slug must fail at pydantic validation, not at write time.

    After the SR-3 fix, max_length on string fields makes the rejection
    happen at record construction with a clear field-level error message,
    instead of triggering the PIPE_BUF guard later in `_append_atomic_line`
    with a confusing low-level ValueError. Shift-left atomicity guarantee.
    """
    with pytest.raises(ValidationError, match="slug"):
        ReviewTelemetryRecord(**{**_BASE_FIELDS, "slug": "x" * 4500})


# ── CLI shape ─────────────────────────────────────────────────────────────────


def _run_cli(stdin: str, *argv: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.review_telemetry", *argv],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        cwd=str(cwd) if cwd else None,
    )


def test_cli_emit_writes_to_observability_dir(tmp_path: Path) -> None:
    payload = json.dumps(_BASE_FIELDS)
    proc = _run_cli(payload, "emit", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    written = tmp_path / DEFAULT_OBSERVABILITY_DIR / f"review-{today}.jsonl"
    assert written.is_file()
    assert proc.stdout.strip() == str(written)


def test_cli_emit_rejects_malformed_input(tmp_path: Path) -> None:
    proc = _run_cli("{not json", "emit", cwd=tmp_path)
    assert proc.returncode == 1
    assert "valid JSON" in proc.stderr or "decode" in proc.stderr


def test_cli_emit_rejects_unknown_subcommand(tmp_path: Path) -> None:
    proc = _run_cli("", "noop", cwd=tmp_path)
    assert proc.returncode == 2
    assert "usage" in proc.stderr
