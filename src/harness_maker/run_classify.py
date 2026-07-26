"""Retroactive run classification: recover stage attribution the transcript never recorded.

`attributionSkill` is dropped the moment a user speaks mid-stage, so 55.9% of priced
turns arrive unlabelled and the largest line in every economics report is
`(unattributed)`. The forward span ledger fixes this going forward; this module
recovers the existing corpus by asking, once per *run boundary*, whether the
unattributed stretch continues the stage that preceded it.

Python owns the cache, the keys and the safe defaults; it never calls an LLM. The
judgment itself belongs to the `/hm:metrics` prose layer (ADR-005).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from .second_opinion_invoke import resolve_base_root
from .stage_spans import ReadDiagnostics

SCHEMA_VERSION = 1

# Bump when the classification PROMPT changes. Verdicts are keyed by
# (boundary uuid, this), so a bump invalidates prior judgments instead of silently
# reusing answers given under different semantics.
CLASSIFIER_VERSION = 1

Verdict = Literal["continuation", "new", "unknown"]
VERDICTS: tuple[str, ...] = ("continuation", "new", "unknown")


class TurnLike(Protocol):
    """Only what boundary detection needs — keeps this module free of the pricing model.

    Read-only members for the same reason as `stage_spans.TurnLike`: a mutable
    protocol attribute is invariant and would reject narrower concrete field types.
    """

    @property
    def attribution_skill(self) -> str | None: ...

    @property
    def session_id(self) -> str: ...

    @property
    def uuid(self) -> str | None: ...

    @property
    def preceded_by_user(self) -> bool: ...

    @property
    def ts(self) -> datetime: ...


class RunBoundary(BaseModel):
    """The first turn of a maximal unattributed stretch within one session."""

    model_config = ConfigDict(strict=True, extra="forbid")

    index: int
    end_index: int
    uuid: str | None
    session_id: str
    preceding_stage: str | None
    has_user_message: bool

    @property
    def turn_count(self) -> int:
        return self.end_index - self.index + 1


class VerdictRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: int
    boundary_uuid: str
    classifier_version: int
    verdict: Verdict
    reason: str = ""
    ts: datetime


class ClassificationAttribution(BaseModel):
    """Per-turn stage assignment plus the counters that keep every gap reportable.

    `cache_misses` and `unknown` are separate because they mean different things to
    the operator: a miss is work not yet done, an unknown is work done that could not
    decide. Both leave the run unattributed.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    stages: tuple[str | None, ...] = ()
    boundaries: int = 0
    cache_misses: int = 0
    unknown: int = 0
    continuations: int = 0


# ------------------------------------------------------------------ cache location


def verdict_cache_path(cwd: Path) -> Path:
    """Always the BASE repo's cache — same seam as the span ledger (ADR-010).

    A cwd-relative path inside `.worktrees/<slug>/` is gitignored churn that
    `task-land` deletes, so a task's accumulated judgments would vanish exactly when
    the task completed.
    """
    return resolve_base_root(cwd) / ".claude" / "observability" / "run-verdicts.jsonl"


def write_verdict(path: Path, record: VerdictRecord) -> Path:
    """Append one verdict. Atomic per `telemetry.py`'s O_APPEND + single-write pattern."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record.model_dump(mode="json")) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
    return path


def read_verdicts(path: Path) -> tuple[dict[tuple[str, int], VerdictRecord], ReadDiagnostics]:
    """Absent cache → empty, never an error. A later record supersedes an earlier one.

    A malformed line is counted and DROPPED rather than repaired: a half-written
    verdict that resolved to `continuation` would move real spend onto a stage that
    did not incur it, and nothing downstream could see that it happened.
    """
    diag = ReadDiagnostics()
    out: dict[tuple[str, int], VerdictRecord] = {}
    if not path.is_file():
        return out, diag
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        diag.total_lines += 1
        try:
            # JSON validation mode, NOT model_validate(json.loads(...)): under
            # strict=True the Python-mode validator rejects an ISO string for a
            # datetime field, so every well-formed line would count as malformed.
            rec = VerdictRecord.model_validate_json(raw)
        except Exception:
            diag.malformed_lines += 1
            continue
        out[(rec.boundary_uuid, rec.classifier_version)] = rec
    return out, diag


# ------------------------------------------------------------------ boundary detection


def find_boundaries(
    turns: Sequence[TurnLike],
    *,
    already_attributed: Sequence[str | None] | None = None,
    capped: frozenset[int] | set[int] | None = None,
) -> list[RunBoundary]:
    """One boundary per maximal unattributed stretch, never spanning a session change.

    Turns are sorted by timestamp across ALL sessions, so the turn physically preceding
    an unattributed one is routinely a peer session's — inheriting across that seam
    would attribute one session's spend to another's stage.

    `already_attributed` lets the caller mark turns a higher-precedence source
    (the span ledger) has already claimed, so they neither open a run nor inflate the
    boundary count that the classification cost is measured against.
    """
    resolved = already_attributed or ((None,) * len(turns))
    capped_set = set(capped or ())

    def _attributed(i: int) -> bool:
        """Capped turns do not OPEN a run — ADR-003's cap is terminal, so a judgment
        about them could never be applied."""
        return turns[i].attribution_skill is not None or resolved[i] is not None or i in capped_set

    def _stage_of(i: int) -> str | None:
        """A capped turn names no stage (review R2-01).

        The first version marked capped indices with the literal `"(capped)"` inside
        `already_attributed`, and this back-scan reads that same sequence — so a capped
        predecessor became `preceding_stage="(capped)"`, the prose layer was asked
        whether the run "continues the stage named `(capped)`", and a `continuation`
        verdict then bucketed real spend under a stage that does not exist.
        """
        if i in capped_set:
            return None
        return turns[i].attribution_skill or resolved[i]

    out: list[RunBoundary] = []
    i = 0
    n = len(turns)
    while i < n:
        if _attributed(i):
            i += 1
            continue
        session = turns[i].session_id
        # Scan back to the nearest attributed turn IN THIS SESSION, not merely to
        # `i - 1` (review M-07). Turns are sorted by ts across all sessions, so under
        # concurrency the physically-preceding turn routinely belongs to a peer — and
        # stopping there reported "nothing to continue", silently disabling inference
        # for exactly the sessions that interleave.
        prev_stage: str | None = None
        for j in range(i - 1, -1, -1):
            if turns[j].session_id != session:
                continue  # a peer session's turn: skip it, never inherit from it
            if j in capped_set:
                # A capped predecessor STOPS the scan (reviews R2-01 + F-03). Skipping
                # past it to the stage before would let inference re-attach the
                # post-cap tail to that stage — extending a span by the back door,
                # which is exactly what ADR-003's terminal cap forbids.
                break
            candidate = _stage_of(j)
            if candidate is not None:
                prev_stage = candidate
                break
            # An UNATTRIBUTED same-session predecessor is not an answer (review R2-04):
            # a peer turn landing inside the stretch splits it, so the fragment before
            # this one is usually another fragment of the same run. Stopping here made
            # every fragment after the first permanently unattributable while still
            # costing an LLM judgment each.
        end = i
        while end + 1 < n and not _attributed(end + 1) and turns[end + 1].session_id == session:
            end += 1
        out.append(
            RunBoundary(
                index=i,
                end_index=end,
                uuid=turns[i].uuid,
                session_id=session,
                preceding_stage=prev_stage,
                has_user_message=turns[i].preceded_by_user,
            )
        )
        i = end + 1
    return out


def attribute_runs(
    turns: Sequence[TurnLike],
    boundaries: Sequence[RunBoundary],
    verdicts: Mapping[tuple[str, int], VerdictRecord],
    *,
    classifier_version: int = CLASSIFIER_VERSION,
    max_turns: int = 400,
    max_min: float = 240.0,
) -> ClassificationAttribution:
    """Apply cached verdicts. Anything unresolved stays unattributed — never inherited.

    ADR-005's asymmetry is the whole design: a wrong `continuation` is invisible
    (spend lands on a stage that did not incur it and the report looks complete),
    while an unattributed run is visible in the `(unattributed)` bucket. So every
    failure mode here — miss, unknown, unparseable, nothing to continue — resolves
    to "leave it alone and count it".
    """
    stages: list[str | None] = [None] * len(turns)
    misses = unknown = continuations = 0

    for boundary in boundaries:
        record = (
            verdicts.get((boundary.uuid, classifier_version)) if boundary.uuid is not None else None
        )
        if record is None:
            misses += 1
            continue
        if record.verdict == "unknown":
            unknown += 1
            continue
        if record.verdict == "new":
            continue  # a resolved answer, not a failure — it must not inflate a counter
        if boundary.preceding_stage is None:
            # A continuation of nothing. Honouring it would require inventing a stage.
            unknown += 1
            continue
        # Bounded, like both sibling attribution paths (review M-09): adjacency caps
        # at 20 turns / 10 min and a span at 400 / 240, each under a comment saying
        # every bound must be able to REJECT. An unbounded inheritance let one
        # `continuation` verdict move an entire overnight stretch onto the preceding
        # stage. Turns past a cap simply stay unattributed — same disposition as a
        # capped span, and visible in `(unattributed)`.
        start_ts = turns[boundary.index].ts
        attributed = 0
        for idx in range(boundary.index, boundary.end_index + 1):
            if attributed >= max_turns:
                break
            if (turns[idx].ts - start_ts).total_seconds() > max_min * 60.0:
                break
            stages[idx] = boundary.preceding_stage
            attributed += 1
        if attributed:
            continuations += 1

    return ClassificationAttribution(
        stages=tuple(stages),
        boundaries=len(boundaries),
        cache_misses=misses,
        unknown=unknown,
        continuations=continuations,
    )


def boundary_inputs(
    turns: Sequence[TurnLike], spans: object
) -> tuple[Sequence[str | None], frozenset[int]]:
    """The single place both entry points derive `find_boundaries` arguments.

    `_cmd_boundaries` and `economics._collect` each built these independently, and when
    the capped-turn handling landed in only one of them the two commands produced
    different boundary UUIDs — so a verdict the prose layer recorded was looked up under
    a key the report never asked for, silently discarded, and counted as a cache miss
    (review R2-02). Same shape as F-01: two entry points, one of them wrong.
    """
    stages: Sequence[str | None] = getattr(spans, "stages", None) or ((None,) * len(turns))
    return stages, frozenset(getattr(spans, "capped_indices", ()) or ())


# ------------------------------------------------------------------ CLI


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _cmd_boundaries(root: Path, transcript_root: Path | None, days: int | None, limit: int) -> int:
    """Emit the UNRESOLVED boundaries only — the bounded work list for the prose layer."""
    from .economics import _load_cli_config
    from .economics_source import load_turns
    from .stage_spans import attribute_turns, ledger_path, read_events

    cfg = _load_cli_config(root)
    result = load_turns(
        root,
        transcript_root=transcript_root,
        days=days if days is not None else cfg.window_days,
    )
    events, _ = read_events(ledger_path(root))
    spans = attribute_turns(
        result.turns, events, max_turns=cfg.span_max_turns, max_min=cfg.span_max_min
    )
    stages, capped = boundary_inputs(result.turns, spans)
    boundaries = find_boundaries(result.turns, already_attributed=stages, capped=capped)
    verdicts, diag = read_verdicts(verdict_cache_path(root))

    pending = [
        b for b in boundaries if b.uuid is not None and (b.uuid, CLASSIFIER_VERSION) not in verdicts
    ]
    _print_json(
        {
            "status": "ok",
            "classifier_version": CLASSIFIER_VERSION,
            "cache_path": str(verdict_cache_path(root)),
            "cache_malformed_lines": diag.malformed_lines,
            "total_boundaries": len(boundaries),
            "unkeyable_boundaries": sum(1 for b in boundaries if b.uuid is None),
            "pending": len(pending),
            "boundaries": [
                {
                    "uuid": b.uuid,
                    "session_id": b.session_id,
                    "turns": b.turn_count,
                    "preceding_stage": b.preceding_stage,
                    "has_user_message": b.has_user_message,
                    "started_at": result.turns[b.index].ts,
                    "ended_at": result.turns[b.end_index].ts,
                }
                for b in pending[:limit]
            ],
        }
    )
    return 0


def _cmd_record(root: Path, boundary_uuid: str, verdict: str, reason: str) -> int:
    path = verdict_cache_path(root)
    write_verdict(
        path,
        VerdictRecord(
            schema_version=SCHEMA_VERSION,
            boundary_uuid=boundary_uuid,
            classifier_version=CLASSIFIER_VERSION,
            verdict=verdict,  # type: ignore[arg-type]
            reason=reason,
            ts=datetime.now(UTC),
        ),
    )
    _print_json({"status": "ok", "recorded": boundary_uuid, "verdict": verdict})
    return 0


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m harness_maker.run_classify")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("boundaries", help="list run boundaries awaiting a verdict")
    listing.add_argument("--root", default=".")
    listing.add_argument("--transcript-root", default=None)
    listing.add_argument("--days", type=int, default=None)
    listing.add_argument("--limit", type=int, default=200)

    record = sub.add_parser("record", help="persist one classification verdict")
    record.add_argument("--root", default=".")
    record.add_argument("--boundary-uuid", required=True)
    # `choices` is the guard: a free-text verdict would be written and then silently
    # dropped by `read_verdicts` as malformed — a write-then-discard with no symptom.
    record.add_argument("--verdict", required=True, choices=VERDICTS)
    record.add_argument("--reason", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    from .command_registry import guard_or_none

    args = argv if argv is not None else sys.argv[1:]
    redirect = guard_or_none("run_classify", args)
    if redirect is not None:
        return redirect
    ns = _build_argparser().parse_args(args)
    # `.resolve()` is load-bearing, not tidiness (review F-01): the rendered command is
    # `--root .`, and an unresolved `Path(".")` encodes to the project dir name `"-"`,
    # which matches nothing under ~/.claude/projects — so `boundaries` returned 0 while
    # `economics report` (which resolves) saw 392 on the same corpus. Every unit test
    # passed an absolute `str(tmp_path)`, which is exactly why none of them saw it.
    root = Path(ns.root).resolve()
    if ns.command == "boundaries":
        return _cmd_boundaries(
            root,
            Path(ns.transcript_root) if ns.transcript_root else None,
            ns.days,
            ns.limit,
        )
    return _cmd_record(root, ns.boundary_uuid, ns.verdict, ns.reason)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
