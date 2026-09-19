"""AC-008/AC-009 — `wall_time_ms` is optional, and optionality is a superset.

`ReviewTelemetryRecord.wall_time_ms` was `int = Field(ge=0)` with no default, while the same
rendered paragraph that documents the emit both claimed round-level numerics default to 0 and
forbade interpolating `wall_time_ms` (determinism leakage). The first emit of every round was
rejected. ADR-005: the schema yields.

AC-009 is a property over the ACCEPTANCE SET, not a spot check: an implementation that made
the field "optional" by renaming or retyping it would satisfy a presence test and violate this.

A.4 (justified passes): `test_negative_wall_time_is_still_rejected`,
`test_previously_valid_records_still_validate` and `test_real_on_disk_rows_still_validate` pass
on the required-field schema by design — they are the SUPERSET half of AC-009 (optional must
not mean unvalidated, and nothing already accepted may become unreadable). They go red if the
change retypes, coerces or un-validates the field. Their RED positive sibling is
`test_record_without_wall_time_ms_validates`, which forces the optionality into existence.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from harness_maker.review_telemetry import ReviewTelemetryRecord


def _base_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "ts": "2026-08-14T00:00:00+00:00",
        "slug": "observed-harness-gaps",
        "round": 1,
        "pass1_n": 3,
        "verifier_kept_n": None,
        "verifier_dropped_n": None,
        "verifier_false_drop_n": None,
        "verifier_false_keep_n": None,
        "fixture_label": None,
        "pass2_kept_n": 3,
        "consensus_passed_n": 2,
        "build_break_count": 0,
        "auto_fix_reverted_n": 0,
        "fallback": None,
        "terminal": False,
        "unreviewed_fix_count": 0,
        "regression_attributed_n": 0,
        "attribution_unknown_n": 0,
    }
    record.update(overrides)
    return record


# --------------------------------------------------------------------------------------
# AC-008 — a record omitting wall_time_ms validates and appends exactly one line
# --------------------------------------------------------------------------------------


def test_record_without_wall_time_ms_validates() -> None:
    model = ReviewTelemetryRecord(**_base_record())  # type: ignore[arg-type]
    assert model.wall_time_ms is None


def test_emit_accepts_record_without_wall_time_ms(tmp_path: Path) -> None:
    """The shipped entry point, not just the model — this is the surface that was rejecting."""
    payload = json.dumps(_base_record())
    # `emit` takes no path flag — it writes relative to cwd. An unrecognised `--root` is
    # silently ignored and the row lands in the REAL repo's observability dir. That happened
    # once while writing this test; isolate via cwd, never via a flag the CLI does not parse.
    result = subprocess.run(
        [sys.executable, "-m", "harness_maker.review_telemetry", "emit"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    written = list((tmp_path / ".claude" / "observability").glob("review-*.jsonl"))
    assert len(written) == 1, f"expected one JSONL, got {written}"
    lines = [line for line in written[0].read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["wall_time_ms"] is None


def test_null_is_distinct_from_zero() -> None:
    """`0` means "measured, instantly"; `None` means "not measured". Never conflate them."""
    measured = ReviewTelemetryRecord(**_base_record(wall_time_ms=0))  # type: ignore[arg-type]
    unmeasured = ReviewTelemetryRecord(**_base_record())  # type: ignore[arg-type]
    assert measured.wall_time_ms == 0
    assert unmeasured.wall_time_ms is None
    assert measured.model_dump()["wall_time_ms"] != unmeasured.model_dump()["wall_time_ms"]


def test_negative_wall_time_is_still_rejected() -> None:
    """Optional must not mean unvalidated — `ge=0` survives."""
    with pytest.raises(ValidationError):
        ReviewTelemetryRecord(**_base_record(wall_time_ms=-1))  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------
# AC-009 (property) — the acceptance set only grew
# --------------------------------------------------------------------------------------


@settings(max_examples=200)
@given(st.integers(min_value=0, max_value=10**9))
def test_previously_valid_records_still_validate(wall_time: int) -> None:
    """Every record that validated under the required-field schema still validates.

    And the parsed value is unchanged — an implementation that "made it optional" by
    coercing, renaming or retyping the field would violate this while passing a
    presence-only check.
    """
    record = _base_record(wall_time_ms=wall_time)
    model = ReviewTelemetryRecord(**record)  # type: ignore[arg-type]
    assert model.wall_time_ms == wall_time
    assert model.model_dump()["wall_time_ms"] == wall_time


def test_real_on_disk_rows_still_validate() -> None:
    """Seeded from real rows: the acceptance set must cover what is already written.

    Resolved at the BASE root: `.claude/observability/` is gitignored, so inside a task
    worktree the test-file-relative path has no rows and this test skipped silently — a
    real-data check that checked nothing on exactly the path every `/hm:` stage runs in.
    """
    from harness_maker.second_opinion_invoke import resolve_base_root

    obs = resolve_base_root(Path(__file__).resolve().parent) / ".claude" / "observability"
    rows = [
        line
        for path in sorted(obs.glob("review-*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        pytest.skip("no review telemetry rows on disk in this checkout")
    for line in rows:
        ReviewTelemetryRecord(**json.loads(line))
