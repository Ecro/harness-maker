"""Per-dispatch ledger for stage-internal subagents — append-only JSONL (ADR-004).

`plan-validator` (34 dispatches, $70) and Phase A.5 `test-reviewer` (42 dispatches, $61)
had **zero** ledger rows. Stage 2's decision on both — keep the second validator pass? keep
the A.5 gate? — depends entirely on data that did not exist. This module is that data.

**One file, two row kinds, explicit discriminators.** `agent` and `stage` are fields, not
filename conventions. The precedent is `second-opinion.jsonl`, where two row kinds shared
`status: "invoked"` and `finding_ref` had to become the discriminator retroactively; an
aggregation that missed the filter silently corrupted skip-rate. Here the discriminator is
present from the first row.

**Written at the BASE repo root, never `Path.cwd()`.** `codex_ledger.main()` used
`project_root=Path.cwd()` and wrote into a gitignored path inside the worktree, so every
row was lost at `task-land`. Rows are useless if they do not survive the stage that wrote
them.

**Pre-registered aggregation (ADR-004).** Recorded here so the ledger is not a denominator
with no numerator — `observability-field-with-no-consumer` is a named failure in this repo:

- Validator: ``P(verdict changes | pass 2 ran)`` = rows with ``pass_or_attempt == 2`` whose
  ``verdict`` differs from the same ``run_id``'s pass-1 row, over all ``pass_or_attempt == 2``
  rows. A low ratio is the evidence for deleting the second pass.
- Phase A.5: ``P(FAIL)`` = rows with ``verdict == "FAIL"`` over all Phase A.5 rows. A low
  ratio is the evidence for deleting the gate.

Both aggregations must filter on ``agent``/``stage`` first, and must exclude the two
dispatch sentinels below — a dispatch that never ran is not an outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from harness_maker import command_registry
from harness_maker.second_opinion_invoke import resolve_base_root

DEFAULT_OBSERVABILITY_DIR = Path(".claude/observability")
LEDGER_FILENAME = "stage-agents.jsonl"
PAYLOAD_DIRNAME = "review-payloads"

#: A dispatch that never produced an outcome. Deliberately NOT `failed` / `skipped`:
#: `test-reviewer`'s own verdict vocabulary contains `FAIL`, and two values differing only
#: by case in one field is the row-kind conflation this repo has already shipped once. The
#: hyphenated prefix cannot collide with any agent verdict.
DISPATCH_SKIPPED = "dispatch-skipped"
DISPATCH_FAILED = "dispatch-failed"
DISPATCH_SENTINELS = frozenset({DISPATCH_SKIPPED, DISPATCH_FAILED})


class StageAgentRow(BaseModel):
    """One dispatch of a stage-internal subagent.

    ``duration_ms`` and ``barrier_index`` are ``| None`` for the reason P1 made the verifier
    counts nullable: ``0`` would read as "measured, and it was instant / segment zero",
    which is a different claim from "this caller did not report it". These rows are
    append-only, so a wrong value is permanent.

    **Why they exist at all** (interview #16): agent latency is not recoverable from the
    transcripts. Dispatch is asynchronous — the tool result returns immediately and the real
    duration arrives out of band — so the harness has zero data on the axis the user
    experiences first. A ``verdict``-only row answers "does the second pass ever change the
    outcome" but never "what does it cost in minutes". ``barrier_index`` records which serial
    segment of the round a dispatch belonged to, which is what turns the
    five-serial-segments-to-three claim into something measurable rather than asserted.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    # max_length guards the PIPE_BUF atomic append at the schema layer, so an oversized
    # field is a clear validation error rather than a late-write ValueError.
    ts: str = Field(max_length=64)
    run_id: str = Field(max_length=128)
    agent: str = Field(max_length=64)
    stage: str = Field(max_length=32)
    slug: str = Field(max_length=200)
    pass_or_attempt: int = Field(ge=1)
    verdict: str = Field(max_length=64)
    terminal: bool
    reason: str | None = Field(default=None, max_length=500)
    duration_ms: int | None = Field(default=None, ge=0)
    barrier_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _a_sentinel_dispatch_is_terminal_and_explained(self) -> StageAgentRow:
        """A dispatch that never ran must say why, and cannot be a non-final attempt.

        Without this, `dispatch-failed` rows accumulate with `reason: null` — which is
        exactly the state `delegation_ledger` is in today (both mismatch rows carry a
        structural null, so no diagnosis exists and P4a had to be created to add one).
        Catching it at the schema is cheaper than a phase.
        """
        if self.verdict in DISPATCH_SENTINELS:
            if not self.reason:
                msg = (
                    f"verdict {self.verdict!r} requires a reason "
                    "naming why the dispatch did not run"
                )
                raise ValueError(msg)
            if not self.terminal:
                msg = (
                    f"verdict {self.verdict!r} cannot be non-terminal — "
                    "the dispatch produced no outcome"
                )
                raise ValueError(msg)
        return self


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_atomic_line(path: Path, line: str) -> None:
    """Append via O_APPEND — kernel-atomic for writes <= PIPE_BUF (4096).

    Mirrors ``review_telemetry`` / ``codex_ledger``: concurrent writers (autoloop + Cursor
    sharing ``.worktrees/``) serialize at the kernel level without explicit locking.
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


def ledger_path(base_root: Path) -> Path:
    return base_root / DEFAULT_OBSERVABILITY_DIR / LEDGER_FILENAME


def _fit(payload: dict[str, Any]) -> str:
    """Serialise, shrinking `reason` until the ENCODED line fits PIPE_BUF.

    `max_length` alone does NOT bound the encoded row, and the comment on the fields once
    claimed it did: the limits sum to ~1052 *characters*, and `ensure_ascii=False` means a
    4-byte-per-character value costs ~4.2 KB — over the 4096 ceiling. This project's default
    locale is non-ASCII, so that is a reachable row, not a theoretical one, and it would
    have raised at write time from a rendered stage line with only `ValidationError` caught.

    Measured, not estimated — re-encode after each cut, so it is correct for any encoding
    width. Mirrors `delegation_ledger._fit`, which was written for this exact case.
    """
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if len(line.encode("utf-8")) + 1 <= 4096:
        return line
    reason = payload.get("reason")
    if not isinstance(reason, str):
        return line  # nothing shrinkable; _append_atomic_line raises, loudly
    keep = len(reason)
    while keep > 0:
        keep //= 2
        line = json.dumps(
            {**payload, "reason": reason[:keep] + "…[truncated]"},
            ensure_ascii=False,
            sort_keys=True,
        )
        if len(line.encode("utf-8")) + 1 <= 4096:
            return line
    return json.dumps({**payload, "reason": "…[truncated]"}, ensure_ascii=False, sort_keys=True)


def emit(row: StageAgentRow, *, base_root: Path) -> Path:
    """Append one row at the BASE root. Returns the path written."""
    path = ledger_path(base_root.resolve())
    _append_atomic_line(path, _fit(row.model_dump()))
    return path


def row_from_dict(data: dict[str, Any], *, auto_timestamp: bool = True) -> StageAgentRow:
    if auto_timestamp and "ts" not in data:
        data = {**data, "ts": _utc_now_iso()}
    return StageAgentRow.model_validate(data)


# ── payload persistence (ADR-006 part 2) ──────────────────────────────────────


_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]")


def _safe_component(value: str, *, field: str) -> str:
    """One path component, allowlisted. Rejects rather than silently mangling to empty.

    `..` is handled explicitly: the character filter alone would pass it through untouched
    (both dots are in the allowlist), which is the traversal this exists to stop.
    """
    cleaned = _SAFE_COMPONENT.sub("-", value)
    if not cleaned or set(cleaned) <= {".", "-"}:
        msg = f"{field}={value!r} has no usable characters for a path component"
        raise ValueError(msg)
    if cleaned != value:
        # The substitution is many-to-one: `a/b` and `a-b` both become `a-b`, and two
        # distinct slugs would then share a payload directory — one silently overwriting
        # the other's rows. A short digest of the RAW value restores injectivity, so a
        # mangled component can still only collide with itself.
        cleaned = f"{cleaned}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]}"
    return cleaned


def persist_payload(
    source: Path,
    *,
    base_root: Path,
    slug: str,
    run_id: str,
    round_n: int,
    reviewer: str,
) -> Path:
    """Copy one reviewer's raw finding payload to the base root, verbatim.

    **This delivers nothing in stage 1 and everything afterwards.** ADR-006's detection
    check failed twice, the second time because `grep -rlE '"severity"\\s*:\\s*"P[0-3]"'`
    over `.claude/observability/` and `work-docs/` returned nothing: this repo has never
    persisted a per-reviewer finding payload anywhere. REVIEW documents are post-consensus
    narrative and `review-*.jsonl` holds counts, so there was no artifact to replay. From
    this landing on, there is one.

    Copied **verbatim and un-parsed** on purpose. A schema here would have to be guessed
    from today's reviewers, and a replay corpus that only accepts the shape it was written
    against is a corpus that stops accepting real inputs the first time a reviewer changes.
    Whole-file write, not the JSONL path: payloads routinely exceed PIPE_BUF, so appending
    them would break the atomicity every other row in this module depends on.
    """
    content = source.read_bytes()
    store = (base_root.resolve() / DEFAULT_OBSERVABILITY_DIR / PAYLOAD_DIRNAME).resolve()
    # ALL THREE components are attacker-reachable, not just `reviewer`. Every one of them is
    # substituted by the model out of rendered template prose, so any of them can carry `..`
    # or `/`. An earlier version sanitised `reviewer` alone and shipped a test asserting "a
    # reviewer name cannot escape the payload directory" — which was true, and covered the
    # one component that was already safe. Reproduced before fixing: `slug='../../../..'`
    # wrote to `/tmp/escaped/…`, outside the store entirely.
    #
    # Every other slug surface in this repo is allowlisted (`worktree._TASK_SLUG_RE`,
    # `spec_need._SLUG_RE`, `memory_md`, `autopilot`); this one was the exception.
    safe_slug = _safe_component(slug, field="slug")
    safe_run_id = _safe_component(run_id, field="run_id")
    safe_reviewer = _safe_component(reviewer, field="reviewer")
    dest_dir = store / safe_slug
    dest = dest_dir / f"{safe_run_id}-round{int(round_n)}-{safe_reviewer}.json"
    # Belt AND braces: sanitising is the rule, containment is the invariant. mkdir follows
    # symlinks, so a sanitised name is not by itself proof the write lands inside the store.
    if not dest.resolve().parent.is_relative_to(store):
        msg = f"payload destination {dest} escapes the store {store}"
        raise ValueError(msg)
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_bytes(content)
    os.replace(tmp, dest)
    return dest


# ── CLI ───────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m harness_maker.stage_agent_ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    # Scalar flags, not argv JSON: CLAUDE.md forbids argv JSON for ledger writes (quoting
    # plus ARG_MAX), and every field here is a short scalar.
    e = sub.add_parser("emit")
    e.add_argument("--run-id", required=True)
    e.add_argument("--agent", required=True)
    e.add_argument("--stage", required=True)
    e.add_argument("--slug", required=True)
    e.add_argument("--pass", dest="pass_or_attempt", type=int, required=True)
    e.add_argument("--verdict", required=True)
    e.add_argument("--terminal", action="store_true")
    e.add_argument("--reason", default=None)
    e.add_argument("--duration-ms", type=int, default=None)
    e.add_argument("--barrier-index", type=int, default=None)

    p = sub.add_parser("persist-payload")
    p.add_argument("--file", required=True, help="path to the reviewer's raw payload")
    p.add_argument("--slug", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--round", dest="round_n", type=int, required=True)
    p.add_argument("--reviewer", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m harness_maker.stage_agent_ledger emit|persist-payload``."""
    guard = command_registry.guard_or_none("stage_agent_ledger", argv)
    if guard is not None:
        return guard
    args = _build_parser().parse_args(list(sys.argv[1:]) if argv is None else list(argv))
    base_root = resolve_base_root(Path.cwd())

    if args.command == "emit":
        try:
            row = row_from_dict(
                {
                    "run_id": args.run_id,
                    "agent": args.agent,
                    "stage": args.stage,
                    "slug": args.slug,
                    "pass_or_attempt": args.pass_or_attempt,
                    "verdict": args.verdict,
                    "terminal": bool(args.terminal),
                    "reason": args.reason,
                    "duration_ms": args.duration_ms,
                    "barrier_index": args.barrier_index,
                }
            )
        except ValidationError as exc:
            sys.stderr.write(f"[stage-agents] row REJECTED, not recorded: {exc}\n")
            return 1
        sys.stdout.write(str(emit(row, base_root=base_root)) + "\n")
        return 0

    source = Path(args.file)
    if not source.is_file():
        # Loud, non-zero: a silently missing payload would leave the replay corpus with a
        # hole that looks exactly like "this round had no findings".
        sys.stderr.write(f"[stage-agents] payload NOT persisted, no such file: {source}\n")
        return 1
    dest = persist_payload(
        source,
        base_root=base_root,
        slug=args.slug,
        run_id=args.run_id,
        round_n=args.round_n,
        reviewer=args.reviewer,
    )
    sys.stdout.write(str(dest) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
