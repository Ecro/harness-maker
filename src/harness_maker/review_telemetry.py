"""Per-`/hm:review` telemetry emitter — append-only JSONL.

PLAN-llm-code-review-2026 ADR-006 specifies a per-session JSONL line keyed
to `.claude/observability/review-{YYYY-MM-DD}.jsonl`. Append uses POSIX
`O_APPEND` so writes ≤ PIPE_BUF (4096 bytes) are kernel-atomic — sufficient
for the 19-field record. Concurrent reviewers (autoloop + Cursor sharing
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

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from harness_maker import command_registry
from harness_maker.conditional_router import KNOWN_LENSES

# Default location relative to project root — overridable via parameter.
DEFAULT_OBSERVABILITY_DIR = Path(".claude/observability")


class ReviewTelemetryRecord(BaseModel):
    """One row appended per `/hm:review` invocation.

    Most **round-level** numeric fields default to 0 (not None) so downstream
    aggregations can sum without null-coalescing. ``fixture_label`` and the two
    ``verifier_false_*`` counts are null on real runs (only labeled-fixture runs
    compute them). ``fallback`` is set only when the verifier model was
    unavailable.

    ``verifier_kept_n`` / ``verifier_dropped_n`` are the exception among the
    round-level counts: they became ``| None`` when the Pass 1.5 dispatch was
    removed, for the same reason as the measure-C fields below. Aggregations over
    a mixed-era ledger must null-coalesce these two.

    The four **measure-C** fields at the bottom deliberately break that default
    (PLAN-review-round-inflation ADR-006/ADR-009): they are ``| None`` so that
    "this harness version never measured it" stays distinguishable from
    "measured zero". Defaulting them to 0 would erase exactly the distinction
    they exist to carry, into append-only rows where a wrong value is permanent.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    # max_length on string fields guards the PIPE_BUF (4096-byte) atomic
    # append at the schema layer, so callers get a clear validation error
    # instead of a confusing late-write ValueError (security-reviewer P2).
    ts: str = Field(max_length=64)
    slug: str = Field(max_length=200)
    round: int = Field(ge=1)
    pass1_n: int = Field(ge=0)
    # Nullable since ADR-001 of PLAN-workflow-loop-efficiency removed the Pass 1.5
    # dispatch. `0` would read as "the verifier ran and dropped nothing", which is
    # the same row-kind conflation already shipped once in second-opinion.jsonl —
    # and these rows are append-only, so a wrong value is permanent. Rows written
    # before the removal keep their integers and still parse.
    verifier_kept_n: int | None = Field(default=None, ge=0)
    verifier_dropped_n: int | None = Field(default=None, ge=0)
    verifier_false_drop_n: int | None = None
    verifier_false_keep_n: int | None = None
    fixture_label: str | None = Field(default=None, max_length=200)
    pass2_kept_n: int = Field(ge=0)
    consensus_passed_n: int = Field(ge=0)
    wall_time_ms: int = Field(ge=0)
    build_break_count: int = Field(ge=0)
    auto_fix_reverted_n: int = Field(ge=0)
    fallback: str | None = Field(default=None, max_length=64)

    # ── measure C (PLAN-review-round-inflation ADR-006 / ADR-009) ────────────
    # `terminal` discriminates the three wire states, because telemetry emits
    # one row per round while these counters are end-of-review quantities:
    #   null  → this harness version never measured (pre-change row)
    #   false → a non-terminal round; the counters below are null
    #   true  → the single terminal row; the counters below carry integers
    terminal: bool | None = None
    unreviewed_fix_count: int | None = Field(default=None, ge=0)
    regression_attributed_n: int | None = Field(default=None, ge=0)
    attribution_unknown_n: int | None = Field(default=None, ge=0)

    # ── declared failure space + confirmation pass (SPEC AC-005 / AC-012) ────
    # `lenses_exercised` doubles as the version discriminator: this harness version never
    # writes it as null (an all-lenses-failed round writes `[]`), so a row carrying it is a
    # post-change row and must be fully readable. Null survives only for legacy rows.
    lenses_exercised: list[str] | None = None
    confirm_pass_ran: bool | None = None
    confirm_pass_new_severe_n: int | None = Field(default=None, ge=0)

    # ── churn measurement (SPEC AC-013, record-only) ─────────────────────────
    # Null across all three = this harness version never measured. The counts are
    # the version discriminator, not the ratio: a round whose whole diff was binary
    # measures nothing and writes `churn_ratio: null` with `churn_measured_n: 0`,
    # which a nullable ratio alone could not tell apart from a legacy row.
    churn_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    churn_max_path: str | None = Field(default=None, max_length=400)
    churn_measured_n: int | None = Field(default=None, ge=0)
    churn_excluded_n: int | None = Field(default=None, ge=0)

    @field_validator("lenses_exercised")
    @classmethod
    def _lenses_are_known(cls, value: list[str] | None) -> list[str] | None:
        """An unrecognised lens name has no reading — this field is the approval gate's input."""
        if value is None:
            return value
        unknown = [lens for lens in value if lens not in KNOWN_LENSES]
        if unknown:
            msg = f"lenses_exercised contains unknown lens name(s): {unknown}"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _confirmation_record_is_readable(self) -> ReviewTelemetryRecord:
        """The three rules of AC-012 — deliberately NOT "both-or-neither".

        Both-or-neither over (ran, count) admitted two unreadable rows: one with all three
        fields absent, byte-identical to a legacy row even when it was this version reporting
        total coverage failure; and `ran=False` beside a numeric count, which has no meaning.
        These rows are append-only, so an unreadable one is permanent.
        """
        if self.lenses_exercised is not None and self.confirm_pass_ran is None:
            msg = "a row carrying lenses_exercised must also carry confirm_pass_ran"
            raise ValueError(msg)
        if self.confirm_pass_ran is not None and self.lenses_exercised is None:
            msg = (
                "a row carrying confirm_pass_ran must also carry lenses_exercised "
                "(use [] when every lens dispatch failed; null means legacy)"
            )
            raise ValueError(msg)
        if self.confirm_pass_ran is True and self.confirm_pass_new_severe_n is None:
            msg = "confirm_pass_new_severe_n is required when confirm_pass_ran is true"
            raise ValueError(msg)
        if self.confirm_pass_ran is not True and self.confirm_pass_new_severe_n is not None:
            msg = "confirm_pass_new_severe_n must be null unless confirm_pass_ran is true"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _churn_record_is_readable(self) -> ReviewTelemetryRecord:
        """The counts are one observation; the ratio is conditional on them.

        A ratio beside absent counts has no denominator to interpret it against,
        and a positive `churn_measured_n` with a null ratio contradicts itself —
        a measured file always yields a number. These rows are append-only.
        """
        if (self.churn_measured_n is None) != (self.churn_excluded_n is None):
            msg = (
                "churn_measured_n and churn_excluded_n are both-or-neither: "
                f"got measured={self.churn_measured_n!r}, excluded={self.churn_excluded_n!r}"
            )
            raise ValueError(msg)
        if self.churn_measured_n is None:
            if self.churn_ratio is not None or self.churn_max_path is not None:
                msg = "churn_ratio/churn_max_path require the churn counts"
                raise ValueError(msg)
            return self
        if self.churn_measured_n > 0 and self.churn_ratio is None:
            msg = f"churn_measured_n={self.churn_measured_n} but churn_ratio is null"
            raise ValueError(msg)
        if self.churn_measured_n == 0 and self.churn_ratio is not None:
            msg = "churn_ratio must be null when no file was measurable"
            raise ValueError(msg)
        if (self.churn_ratio is None) != (self.churn_max_path is None):
            msg = "churn_ratio and churn_max_path are both-or-neither"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _verifier_counts_are_both_or_neither(self) -> ReviewTelemetryRecord:
        """Nullability must not newly admit a shape the integers made impossible.

        The pair is one observation: either the Pass 1.5 verifier ran (both counts) or
        it does not exist (neither). One set and one absent has no reading, and these
        rows are append-only — an incoherent row cannot be repaired after the fact.
        """
        if (self.verifier_kept_n is None) != (self.verifier_dropped_n is None):
            msg = (
                "verifier_kept_n and verifier_dropped_n are both-or-neither: "
                f"got kept={self.verifier_kept_n!r}, dropped={self.verifier_dropped_n!r}"
            )
            raise ValueError(msg)
        return self


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
    _guard = command_registry.guard_or_none("review_telemetry", argv)
    if _guard is not None:
        return _guard
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
