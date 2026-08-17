"""Phase A4 — review telemetry emitter unit tests.

ADR-006 contract (PLAN-llm-code-review-2026), extended by PLAN-review-round-inflation
ADR-006/ADR-009 with measure C's three counters plus the `terminal` discriminator:
- 19 fields, 8 nullable. Null never means zero — see the wire-state test below.
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
from typing import Any

import pytest
from pydantic import ValidationError

from harness_maker.review_telemetry import (
    DEFAULT_OBSERVABILITY_DIR,
    ReviewTelemetryRecord,
    emit,
    record_from_dict,
)

_BASE_FIELDS: dict[str, Any] = {
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


def test_emit_absolute_observability_dir_inside_project_root_allowed(
    tmp_path: Path,
) -> None:
    """An absolute observability_dir that lies inside project_root resolves."""
    rec = ReviewTelemetryRecord(**_BASE_FIELDS)
    abs_inside = tmp_path / "custom-observability"
    path = emit(rec, project_root=tmp_path, observability_dir=abs_inside)
    assert path.is_file()
    assert path.parent == abs_inside.resolve()


def test_emit_absolute_observability_dir_outside_project_root_rejected(
    tmp_path: Path,
) -> None:
    """An absolute observability_dir that escapes project_root must raise.

    Regression for release-0-10-0 REVIEW O2: previously an absolute base_dir
    was used directly without containment validation, so an internal caller
    passing an attacker-influenced absolute path could write JSONL anywhere
    on the filesystem the process had write access to.
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    escape_target = tmp_path / "outside"
    escape_target.mkdir()
    rec = ReviewTelemetryRecord(**_BASE_FIELDS)

    with pytest.raises(ValueError, match="escapes project_root"):
        emit(rec, project_root=project_root, observability_dir=escape_target)


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


# ── PLAN-review-round-inflation ADR-006 / ADR-009 ────────────────────────────
#
# Four optional fields carry measure C. They are `| None`, never `int = 0`,
# because "this harness version never measured it" must stay distinguishable
# from "measured zero" — the absent-case failure CLAUDE.md records as this
# project's most-recurring class. `terminal` is the discriminator that makes
# the non-terminal rounds' nulls readable (ADR-009): telemetry emits one row
# per round, but the three counters are end-of-review quantities.


def test_pre_change_row_validates_with_the_new_fields_absent() -> None:
    """A row written by a harness that predates measure C must still validate.

    `_BASE_FIELDS` is literally that shape — it was the whole record before
    this change.
    """
    rec = ReviewTelemetryRecord(**_BASE_FIELDS)
    assert rec.unreviewed_fix_count is None
    assert rec.regression_attributed_n is None
    assert rec.attribution_unknown_n is None
    assert rec.terminal is None


def test_absent_counters_are_none_not_zero() -> None:
    """ADR-006: 0 means measured-zero. Defaulting to 0 would erase the
    distinction that the field exists to preserve."""
    rec = ReviewTelemetryRecord(**_BASE_FIELDS)
    for value in (
        rec.unreviewed_fix_count,
        rec.regression_attributed_n,
        rec.attribution_unknown_n,
    ):
        assert value is None
        assert value != 0  # guards a future `int = 0` regression


def test_the_three_wire_states_are_distinguishable() -> None:
    """ADR-009. `emit` serializes `model_dump()` unconditionally, so optional
    fields are always present on the wire as explicit null — key presence can
    therefore never discriminate. `terminal` is what does."""
    unmeasured = ReviewTelemetryRecord(**_BASE_FIELDS).model_dump()
    non_terminal = ReviewTelemetryRecord(**{**_BASE_FIELDS, "terminal": False}).model_dump()
    terminal = ReviewTelemetryRecord(
        **{
            **_BASE_FIELDS,
            "terminal": True,
            "unreviewed_fix_count": 3,
            "regression_attributed_n": 2,
            "attribution_unknown_n": 0,
        }
    ).model_dump()

    counters = ("unreviewed_fix_count", "regression_attributed_n", "attribution_unknown_n")

    # The discriminator separates the three states.
    assert unmeasured["terminal"] is None
    assert non_terminal["terminal"] is False
    assert terminal["terminal"] is True

    # The counters must be null ON THE WIRE for both non-measuring states — not
    # merely present. An implementation that coerces null→0 during serialization
    # (a field_serializer, a model_dump override, a dump-path default) would pass
    # every attribute-level test in this file while destroying ADR-006's
    # distinction in the append-only rows, where a wrong value is permanent.
    for field in counters:
        assert unmeasured[field] is None, f"{field} must stay null for an unmeasured row"
        assert non_terminal[field] is None, f"{field} must stay null on a non-terminal round"

    # An aggregation filters on `terminal is True` and gets only measured rows.
    measured = [r for r in (unmeasured, non_terminal, terminal) if r["terminal"] is True]
    assert measured == [terminal]
    assert measured[0]["attribution_unknown_n"] == 0  # measured zero survives


def test_counters_accept_zero_and_reject_negative() -> None:
    """The accept-0 arm is load-bearing: without it this test passes before the
    fields exist at all (`extra=forbid` raises for an unknown key), so it would
    be green in both directions and could not see the `ge=0` constraint."""
    for field in (
        "unreviewed_fix_count",
        "regression_attributed_n",
        "attribution_unknown_n",
    ):
        accepted = ReviewTelemetryRecord(**{**_BASE_FIELDS, field: 0})
        assert getattr(accepted, field) == 0
        with pytest.raises(ValidationError) as exc:
            ReviewTelemetryRecord(**{**_BASE_FIELDS, field: -1})
        assert "greater_than_equal" in str(exc.value)


def test_terminal_row_survives_the_round_trip(tmp_path: Path) -> None:
    """The counters must be readable back off disk, not just constructible."""
    rec = ReviewTelemetryRecord(
        **{
            **_BASE_FIELDS,
            "terminal": True,
            "unreviewed_fix_count": 6,
            "regression_attributed_n": 4,
            "attribution_unknown_n": 1,
        }
    )
    path = emit(rec, project_root=tmp_path, observability_dir=Path("obs"))
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["terminal"] is True
    assert row["unreviewed_fix_count"] == 6
    assert row["regression_attributed_n"] == 4
    assert row["attribution_unknown_n"] == 1


def test_unmeasured_counters_stay_null_on_disk(tmp_path: Path) -> None:
    """The wire-state test reads `model_dump()`, which is today's emit path
    (`review_telemetry.py:144`). This one reads the FILE, so a future switch to
    `model_dump_json()` with a `when_used="json"` serializer — or a
    `json.dumps(default=…)` — cannot coerce null→0 into the permanent
    append-only rows while every in-memory assertion stays green."""
    path = emit(
        ReviewTelemetryRecord(**_BASE_FIELDS),
        project_root=tmp_path,
        observability_dir=Path("obs"),
    )
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["terminal"] is None
    for field in ("unreviewed_fix_count", "regression_attributed_n", "attribution_unknown_n"):
        assert row[field] is None, f"{field} was coerced away from null on disk"
