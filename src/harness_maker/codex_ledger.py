"""Second-opinion calibration ledger — append-only JSONL (PLAN-crossmodel-codex-gaps ADR-005,
generalized to multi-vendor by PLAN-second-opinion-multi-model ADR-005).

Records every second-opinion disposition (and every skip/failure) so skip-rate and
per-project precision can be tracked over time, per `model`. Unlike ``review_telemetry``
this is a single non-partitioned file — the ledger is a cross-time, cross-vendor calibration
record, not a per-day log.

**Two row kinds share this file. Filter before aggregating.**

- ``finding_ref == "n/a"`` → a **per-invocation** row: one per second-opinion CLI call,
  recording that the call happened and how it went. This is the denominator for the
  degradation rate: ``(skipped + failed) / total`` **per model**, excluding
  ``stage == "health"`` rows (the smoke test runs a trivial prompt from the base cwd and is
  structurally biased toward ``invoked``). ``failed`` belongs in the numerator: the CLI ran
  but returned a payload Step 4 cannot consume, so that model's voice is missing from the
  review exactly as if it had been skipped. Aggregating over ``skipped`` alone reports a
  fraction of the real degradation, and aggregating across models lets a healthy one mask a
  broken one — observed 2026-08-06, where ``skipped/total`` read 10.3% against a true 20.7%
  and one model's entire loss sat in ``failed`` rows.
- ``finding_ref != "n/a"`` → a **per-finding disposition** row: one per finding the review
  stage's PIDA gate adjudicated, carrying the stable finding id, the disposition, and the
  capped ``oracle_result`` rationale. This is the numerator/denominator pair for
  acceptance-rate.

Both kinds carry ``status: "invoked"``, so ``finding_ref`` is the ONLY discriminator. An
aggregation that skips this filter counts every finding as another invocation and silently
corrupts skip-rate — the same denominator hazard that already changed once under this file.

``oracle_result`` was a nullable placeholder through v1 and is now **populated on per-finding
rows** (PLAN-second-opinion-acceptance-gate ADR-005) with a ``cap_oracle_result``-capped
verdict + evidence string. It stays ``None`` on per-invocation, skip and failure rows.
``later_regression_link`` remains a nullable placeholder.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from harness_maker import command_registry

DEFAULT_OBSERVABILITY_DIR = Path(".claude/observability")
LEDGER_FILENAME = "second-opinion.jsonl"
_LEGACY_LEDGER_FILENAME = "codex-second-opinion.jsonl"


class SecondOpinionRecord(BaseModel):
    """One ledger row per second-opinion finding disposition (or one skip/failure row).

    ``model`` / ``status`` / ``disposition`` / ``stage`` are closed enums so the
    skip-rate aggregation stays parseable and cross-vendor comparable. ``skip_reason``
    is null on the invoked path. ``oracle_result`` carries the PIDA rationale on
    per-finding rows (see the module docstring's two-row-kind note) and is null on every
    other kind; ``later_regression_link`` is still deferred (always null).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    ts: str = Field(max_length=64)
    slug: str = Field(max_length=200)
    stage: Literal["review", "plan", "health"]
    model: Literal["codex", "antigravity"] = "codex"
    finding_ref: str = Field(max_length=500)
    disposition: Literal["accepted", "rejected", "duplicate", "unresolved"]
    status: Literal["invoked", "skipped", "failed"]
    skip_reason: str | None = Field(default=None, max_length=500)
    oracle_result: str | None = Field(default=None, max_length=200)
    later_regression_link: str | None = Field(default=None, max_length=500)
    # Wall-clock seconds for ONE invocation, measured by the invoker around
    # `subprocess.run` — not read from a model's own envelope, so codex and every
    # exception branch are covered by the same code. `None` on per-finding disposition
    # rows (they measure nothing) and on rows written before this field existed, which
    # is why it must NOT appear in the shipped schema's `required` list.
    duration_s: float | None = None


def _utc_now_iso() -> str:
    """ISO 8601 second-resolution UTC stamp — deterministic for test override."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


ORACLE_RESULT_MAX = 200


def cap_oracle_result(verdict: str, evidence: str | None) -> str:
    """Build a ``oracle_result`` value that CANNOT lose its row to the length constraint.

    WHY a cap rather than letting validation reject: on the invoker path row emission
    swallows every exception by contract, so an over-length value does not raise — it
    deletes the whole row with no diagnostic. Truncating first turns a silent loss into a
    visible ellipsis. The marker is load-bearing: a silently-clipped rationale reads as
    complete evidence to whoever audits the refutation later.
    """
    if not evidence:
        return verdict[:ORACLE_RESULT_MAX]
    prefix = f"{verdict}: "
    if len(prefix) >= ORACLE_RESULT_MAX:
        return prefix[:ORACLE_RESULT_MAX]
    room = ORACLE_RESULT_MAX - len(prefix)
    if len(evidence) <= room:
        return prefix + evidence
    return prefix + evidence[: room - 1] + "…"


def _append_atomic_line(path: Path, line: str) -> None:
    """Append a single line via O_APPEND — kernel-atomic for writes <= PIPE_BUF (4096).

    Mirrors ``review_telemetry._append_atomic_line``: concurrent writers (autoloop +
    Cursor sharing ``.worktrees/``) serialize at the kernel level without locking.
    """
    payload = line if line.endswith("\n") else line + "\n"
    encoded = payload.encode("utf-8")
    if len(encoded) > 4096:
        raise ValueError(
            f"ledger line {len(encoded)} bytes exceeds PIPE_BUF (4096); "
            "trim field content to preserve append atomicity"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        view = memoryview(encoded)
        written = 0
        while written < len(view):
            n = os.write(fd, view[written:])
            if n == 0:
                raise OSError("os.write returned 0 on ledger append")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)


def _migrate_legacy_ledger(base_dir: Path) -> None:
    """One-time forward-copy of the legacy single-vendor ledger (ADR-005).

    If the legacy ``codex-second-opinion.jsonl`` exists and the new ``second-opinion.jsonl``
    does not, copy every legacy row forward tagged ``model="codex"`` (the legacy file predates
    the ``model`` field, so every row it contains is implicitly a Codex row). Idempotent: a
    no-op once the new file exists, regardless of legacy content — this is a ONE-TIME migration,
    never a repeated merge. Malformed legacy rows are skipped (best-effort; never raises).
    """
    legacy_path = base_dir / _LEGACY_LEDGER_FILENAME
    new_path = base_dir / LEDGER_FILENAME
    if new_path.exists() or not legacy_path.exists():
        return
    lines: list[str] = []
    for raw_line in legacy_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            data = json.loads(raw_line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        data.setdefault("model", "codex")
        # Legacy rows used `codex_status`; the new shape is `status`.
        if "codex_status" in data and "status" not in data:
            data["status"] = data.pop("codex_status")
        try:
            record = SecondOpinionRecord.model_validate(data)
        except ValidationError:
            continue
        lines.append(json.dumps(record.model_dump(), ensure_ascii=False, sort_keys=True))
    if not lines:
        return
    new_path.parent.mkdir(parents=True, exist_ok=True)
    for line in lines:
        _append_atomic_line(new_path, line)


def emit(
    record: SecondOpinionRecord,
    *,
    project_root: Path | None = None,
    observability_dir: Path | None = None,
) -> Path:
    """Append one ledger row. Returns the path written.

    ``observability_dir`` is joined onto ``project_root`` when relative; an absolute
    ``observability_dir`` must stay within ``project_root`` (containment guard mirrors
    ``review_telemetry.emit`` — prevents config-influenced writes outside the tree).
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
    _migrate_legacy_ledger(base_dir)
    path = base_dir / LEDGER_FILENAME
    line = json.dumps(record.model_dump(), ensure_ascii=False, sort_keys=True)
    _append_atomic_line(path, line)
    return path


def record_from_dict(
    data: dict[str, Any],
    *,
    auto_timestamp: bool = True,
) -> SecondOpinionRecord:
    """Validate a raw dict against the ledger schema, optionally stamping ``ts``."""
    if auto_timestamp and "ts" not in data:
        data = {**data, "ts": _utc_now_iso()}
    return SecondOpinionRecord.model_validate(data)


PER_INVOCATION_REF = "n/a"
#: Mirrors the `disposition` Literal above. Kept next to the aggregation so a new enum value
#: shows up in the counts rather than being silently dropped into no bucket.
DISPOSITION_VALUES: frozenset[str] = frozenset({"accepted", "rejected", "duplicate", "unresolved"})


def load_ledger(path: Path | str) -> list[dict[str, Any]]:
    """Every parseable row, in file order. An absent file is an empty ledger, not an error.

    Unparseable lines are skipped rather than raising: the file is append-only from several
    writers, so a torn final line during a concurrent write must not make the whole history
    unreadable. Anything that does parse is returned as-is — filtering is the caller's job, and
    the two row kinds share this file.
    """
    p = Path(path)
    if not p.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def disposition_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The per-finding rows only.

    `finding_ref` is the ONLY discriminator — both kinds carry `status: "invoked"` — and the
    filter is the whole point of this helper existing rather than each caller writing the
    comparison itself. Getting it wrong does not raise; it counts every finding as another
    invocation and silently moves a rate, which is how this file's denominator changed once
    already.
    """
    return [r for r in rows if r.get("finding_ref", PER_INVOCATION_REF) != PER_INVOCATION_REF]


def rejection_rate(rows: list[dict[str, Any]]) -> float:
    """Rejected share of adjudicated findings. `0.0` when nothing has been adjudicated.

    Zero rather than a division error: an empty ledger means the gate has not run, and a
    caller reading a rate should see "none rejected", not a traceback in the middle of a
    review.
    """
    findings = disposition_rows(rows)
    if not findings:
        return 0.0
    rejected = sum(1 for r in findings if r.get("disposition") == "rejected")
    return rejected / len(findings)


def disposition_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Per-disposition tally over the per-finding rows, with every enum value present."""
    counts = dict.fromkeys(sorted(DISPOSITION_VALUES), 0)
    for row in disposition_rows(rows):
        value = str(row.get("disposition", ""))
        if value in counts:
            counts[value] += 1
    return counts


# -- CLI -----------------------------------------------------------------------

# Arg-based fields (REVIEW security P1): the rendered recipe passes each value as a
# SEPARATE argv element via "$var", so argparse — not the shell — owns the content.
# This removes the inline `echo '{...<untrusted>...}'` shell-quoted-blob injection
# vector. The stdin JSON path is kept for programmatic callers/tests.
_ARG_FIELDS: tuple[str, ...] = (
    "slug",
    "stage",
    "model",
    "finding-ref",
    "disposition",
    "status",
    "skip-reason",
    "oracle-result",
    "later-regression-link",
)


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m harness_maker.codex_ledger")
    sub = parser.add_subparsers(dest="cmd", required=True)
    emit_parser = sub.add_parser("emit", help="append one ledger row")
    for field_flag in _ARG_FIELDS:
        emit_parser.add_argument(f"--{field_flag}", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI: ``emit`` from explicit ``--field`` args (injection-safe) OR a JSON object on stdin.

    When any ``--field`` flag is present the row is built from argv (each value a
    separate, shell-quoted argument); otherwise a JSON object is read from stdin.
    """
    _guard = command_registry.guard_or_none("codex_ledger", argv)
    if _guard is not None:
        return _guard
    args = list(sys.argv[1:]) if argv is None else list(argv)
    if not args or args[0] != "emit":
        sys.stderr.write("usage: python -m harness_maker.codex_ledger emit [--slug ...|stdin]\n")
        return 2

    ns = _build_argparser().parse_args(args)
    arg_data = {
        key.replace("-", "_"): getattr(ns, key.replace("-", "_"))
        for key in _ARG_FIELDS
        if getattr(ns, key.replace("-", "_")) is not None
    }

    if arg_data:
        data: dict[str, Any] = arg_data
    else:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.stderr.write("emit: no --field args and stdin is empty\n")
            return 1
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            sys.stderr.write(f"emit: stdin is not valid JSON: {exc}\n")
            return 1
        if not isinstance(parsed, dict):
            sys.stderr.write("emit: stdin must decode to a JSON object\n")
            return 1
        data = parsed

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
