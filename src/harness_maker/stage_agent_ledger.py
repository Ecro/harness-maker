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

- Validator: ``P(verdict changes | a later pass ran)`` = rows with ``pass_or_attempt >= 2``
  whose ``verdict`` differs from the same ``run_id``'s pass-1 row, over all
  ``pass_or_attempt >= 2`` rows. A low ratio is the evidence for deleting the second pass.
- Phase A.5: ``P(FAIL)`` = rows with ``verdict == "FAIL"`` over all Phase A.5 rows. A low
  ratio is the evidence for deleting the gate.

Both aggregations must filter on ``agent``/``stage`` first, and must exclude the two
dispatch sentinels below — a dispatch that never ran is not an outcome.

**AMENDMENT, 2026-08-07 — recorded because a silent amendment defeats pre-registration.**
The validator rule originally read ``pass_or_attempt == 2``, an equality that assumed the
documented cap ("re-run validator once only") held. The first six rows contained a run
(``msms-20260807-1``) with a THIRD pass — three genuine dispatches 15.1 and 4.9 minutes
apart, not a mislabeled row — so the equality was silently dropping the case most likely to
carry a changed verdict: passes 1 and 2 had already agreed, and only pass 3 could
disagree with them.

**The justification is correctness, and the protection is disclosure — nothing else.**
An earlier version of this note claimed the amendment was "conservative" because a larger
denominator makes "the later pass never changes the verdict" harder to demonstrate. **That
was false, and false in the direction that flattered the amendment.** The row admitted by
the widening was already known to AGREE with pass 1, so 0/2 became 0/3: the observed rate
is unchanged and its upper confidence bound is tighter, which makes the deletion case
*stronger*, not weaker. Widening a population only raises the bar when the added rows are
numerator-eligible in expectation, and that had already been ruled out by inspection.
Review caught this; it is recorded rather than quietly corrected, because a pre-registration
whose audit trail contains a flattering falsehood is worse than one with no argument at all.

What actually justifies it:
1. **The equality was wrong about the world.** It silently discarded real observations, so
   it did not measure the question it was registered to answer. That is a defect, not a
   preference, and correcting it does not depend on which way the numbers then move.
2. **Disclosure.** It was made after observing the pass-3 row, and that is stated here
   rather than inferred from a diff. The reader can therefore discount it appropriately —
   which is the only real protection available once a rule is amended post-hoc.

The equality also produced one real reporting error before it was caught: an aggregation was
reported as "0/3" while the registered rule specified a denominator of 2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Sequence
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
    def _a_sentinel_dispatch_is_explained(self) -> StageAgentRow:
        """A dispatch that never ran must say why.

        Without this, `dispatch-failed` rows accumulate with `reason: null` — which is
        exactly the state `delegation_ledger` is in today (both mismatch rows carry a
        structural null, so no diagnosis exists and P4a had to be created to add one).
        Catching it at the schema is cheaper than a phase.

        **`terminal` is NOT forced here, and an earlier version forcing it was wrong.**
        It reasoned that "a dispatch that produced no outcome cannot be a non-final
        attempt" — but a launch failure is precisely the case the caller retries, and
        `plan.md.j2` explicitly instructs a retry after one. Forcing `terminal=True` made
        the mandated shape (`pass 1 dispatch-failed`, `pass 2 succeeds`) record TWO
        terminal rows, which `check_run_coherence` then had to flag. The schema was
        manufacturing the incoherence the checker reported.
        """
        if self.verdict in DISPATCH_SENTINELS and not self.reason:
            msg = f"verdict {self.verdict!r} requires a reason naming why the dispatch did not run"
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


# ── cross-row coherence (F-B) ─────────────────────────────────────────────────


class RunCoherence(BaseModel):
    """What a single (agent, run_id) group looks like, and whether it is readable.

    The row validator cannot express any of this: it sees one row, and every defect here is
    a relationship BETWEEN rows. That is not a gap that can be closed by tightening the
    schema — it has to be checked where rows are read back.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    agent: str
    stage: str
    slug: str
    run_id: str
    passes: tuple[int, ...]
    terminal_count: int
    problems: tuple[str, ...]
    incomplete: bool = False

    @property
    def ok(self) -> bool:
        """`incomplete` deliberately does NOT make a run not-ok — see `check_run_coherence`."""
        return not self.problems


def check_run_coherence(rows: list[dict[str, Any]]) -> list[RunCoherence]:
    """Group rows by (agent, stage, slug, run_id) and report the incoherent groups.

    **Run this before any aggregation** — `hm stage_agent_ledger coherence` is the CLI.
    A run with two `terminal` rows has no single "the dispatch that ended it", so any read
    keyed on terminal picks one arbitrarily and reports a number nobody can reproduce.
    That is not hypothetical: `msms-20260807-1` shipped with passes 1/2/3 and terminal on
    both 2 and 3, in the first six rows this ledger ever held.

    **The key is all four fields, not `(agent, run_id)`.** `run_id` is chosen by the model
    and nothing enforces global uniqueness, so an id reused across stages or slugs merged
    independent runs and produced fabricated "duplicate pass" / "multiple terminal"
    reports — a checker inventing the defects it exists to find.

    **Sentinel rows COUNT as passes.** An earlier version excluded them, reasoning that a
    dispatch which never ran has no place in the sequence. The opposite is true: a launch
    failure occupies an attempt number, and the retry the guidance mandates is the *next*
    one — so excluding it turned the mandated `[failed, retried]` shape into the gap
    `(2,)` and flagged it. They are attempts; only their outcome is missing.

    Never raises on bad input: rows come from a shared append-only file that concurrent
    sessions write and a human can hand-edit, and one unreadable line must not void the
    report for every other run.
    """
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    unreadable: dict[tuple[str, str, str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("agent")),
            str(row.get("stage")),
            str(row.get("slug")),
            str(row.get("run_id")),
        )
        groups.setdefault(key, []).append(row)

    out: list[RunCoherence] = []
    for key, rs in sorted(groups.items()):
        agent, stage, slug, run_id = key
        passes: list[int] = []
        bad = 0
        for r in rs:
            raw = r.get("pass_or_attempt")
            if isinstance(raw, bool) or not isinstance(raw, int | str):
                bad += 1
                continue
            try:
                passes.append(int(raw))
            except (TypeError, ValueError):
                bad += 1
        unreadable[key] = bad
        # `terminal` is compared to True rather than tested for truthiness: the string
        # "false" is truthy, and these rows arrive from JSON a human may have edited.
        terminal_rows = [r for r in rs if r.get("terminal") is True]
        ordered = tuple(sorted(passes))

        problems: list[str] = []
        if bad:
            problems.append(f"{bad} row(s) have an unreadable `pass_or_attempt`")
        if len(terminal_rows) > 1:
            problems.append(
                f"{len(terminal_rows)} terminal rows — no single row ends this run, so any "
                "aggregation keyed on `terminal` is reading an arbitrary one"
            )
        # NOT a `problem`: a run still in flight has no terminal row yet, and this repo
        # runs many sessions at once. Reporting it as a defect would make the CLI exit 1
        # whenever a peer is mid-run — the boy-who-cried-wolf failure that gets a gate
        # ignored. Surfaced as `incomplete` instead, which the CLI prints but does not fail on.
        incomplete = not terminal_rows
        if len(set(ordered)) != len(ordered):
            problems.append(f"duplicate pass numbers {ordered} — a retry overwrote its own slot")
        if ordered and ordered != tuple(range(1, len(ordered) + 1)):
            problems.append(f"pass numbers are not 1..N: {ordered}")
        if len(terminal_rows) == 1 and ordered:
            last = terminal_rows[0].get("pass_or_attempt")
            if isinstance(last, int) and not isinstance(last, bool) and last < max(ordered):
                problems.append(
                    f"the terminal row is pass {last} but the run continues to {max(ordered)}"
                )

        out.append(
            RunCoherence(
                agent=agent,
                stage=stage,
                slug=slug,
                run_id=run_id,
                passes=ordered,
                terminal_count=len(terminal_rows),
                problems=tuple(problems),
                incomplete=incomplete,
            )
        )
    return out


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


# ── reconcile: is the ledger corroborated by the transcript? ──────────────────


class ReconcileResult(BaseModel):
    """One project's ledger count set against what its transcript actually shows."""

    model_config = ConfigDict(strict=True, extra="forbid")

    ledger_dispatches: int
    turn_groups: int
    agrees: bool
    reason: str | None = None


def sidechain_turn_groups(turns: Sequence[Any]) -> int:
    """Count maximal contiguous runs of sidechain turns in a globally-interleaved timeline.

    **This is NOT a dispatch count, and must not be read as one.** ``load_turns`` performs one
    global sort across every discovered directory, session and worktree sibling, so contiguity
    carries no dispatch-boundary semantics. It is wrong in **both** directions:

    - **Undercount.** Reviewers are dispatched as a parallel batch in one message, and the main
      loop emits no turn until the batch returns — so N concurrent subagents form ONE run.
      This does NOT currently corrupt the recorded population: the only rendered emit sites are
      ``plan.md.j2`` (``--agent plan-validator``) and ``execute.md.j2`` (``--agent
      test-reviewer``), both single dispatches separated by main-chain turns. An earlier version
      of this note claimed ``code-reviewer`` was a recorded agent and therefore batched into the
      denominator; ``rg -o -- '--agent [a-z-]+' src/harness_maker/templates`` refutes that — the
      few ``code-reviewer`` rows in the corpus did not come from a rendered site. Adding a
      batched emit site later WOULD make this bite.
    - **Overcount.** A peer session working the same project contributes main-scope turns into
      the same sorted list, splitting one real dispatch into several runs.

    It is used anyway because it is *reproducible*: the ``{(session_id, stage)}`` key the first
    draft used was computed by hand in a shell one-liner and merged every dispatch of one agent
    in one session. Neither key is a dispatch count; this one at least has a definition a test
    can pin. ``reconcile_counts`` is deliberately built to survive that — see its docstring.

    ``Sequence[Any]`` rather than ``Sequence[TurnRecord]``: the tests pass a two-attribute fake
    so this stays independent of the transcript reader, and importing ``TurnRecord`` here would
    pull ``economics`` into a module the CLI deliberately imports lazily.
    """
    ordered = sorted(turns, key=lambda t: t.ts)
    groups = 0
    in_run = False
    for turn in ordered:
        if turn.scope == "subagent":
            if not in_run:
                groups += 1
                in_run = True
        else:
            in_run = False
    return groups


def reconcile_counts(
    rows: Sequence[dict[str, Any]], *, subagent_turn_groups: int
) -> ReconcileResult:
    """Compare recorded dispatches against observed ones, flagging only what is decidable.

    ``ledger <= groups`` is the EXPECTED relation, not loss: the ledger records only the
    gated dispatches its stages emit (today ``plan-validator`` and ``test-reviewer``), never
    every subagent. Two
    shapes are therefore flagged, and only two — the ones a pair of scalars can actually
    carry. **Partial loss is invisible to this predicate** (3 recorded of 40 real reads as
    agreement, and no inequality over these two numbers can tell that from "3 gated dispatches
    plus 37 other subagents"). Restricting the denominator to the three recorded agent names
    would convert ``<=`` into ``==`` and make partial loss visible; that is deliberately not
    done here, and the blindness is recorded in the wiki entry so a ``ledger-trustworthy: yes``
    is not read as more than it is.

    Dispatch sentinels are excluded: a dispatch that never ran cannot have left a turn-group,
    so counting it would invert the test and report a run of launch failures as loss.
    """
    dispatches = sum(1 for row in rows if row.get("verdict") not in DISPATCH_SENTINELS)
    if dispatches == 0 and subagent_turn_groups > 0:
        return ReconcileResult(
            ledger_dispatches=0,
            turn_groups=subagent_turn_groups,
            agrees=False,
            reason=(
                f"{subagent_turn_groups} subagent dispatch(es) observed in the transcript "
                "but the ledger recorded none"
            ),
        )
    if dispatches > subagent_turn_groups:
        return ReconcileResult(
            ledger_dispatches=dispatches,
            turn_groups=subagent_turn_groups,
            agrees=False,
            reason=(
                f"ledger recorded {dispatches} dispatch(es) but only "
                f"{subagent_turn_groups} were observed — transcript loss, a double-terminal "
                "run inflating the count, or fabrication"
            ),
        )
    return ReconcileResult(
        ledger_dispatches=dispatches, turn_groups=subagent_turn_groups, agrees=True
    )


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

    # F5: without this the checker had NO caller — no CLI, no rendered guidance, only
    # tests. A checker nobody can run is `observability-field-with-no-consumer` one layer
    # up, which is the exact failure this module's docstring names.
    c = sub.add_parser("coherence")
    c.add_argument("--quiet", action="store_true", help="print only incoherent runs")

    r = sub.add_parser(
        "reconcile",
        help=(
            "DIAGNOSTIC ONLY — exit 0 agrees, 2 disagrees (can be expected + permanent), "
            "1 tool failure. Never wire this into a gate (PLAN A2)"
        ),
    )
    r.add_argument("--root", default=".")

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

    if args.command == "coherence":
        path = ledger_path(base_root)
        if not path.is_file():
            sys.stdout.write(f"coherence: no ledger at {path}\n")
            return 0
        rows: list[dict[str, Any]] = []
        malformed = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except ValueError:
                malformed += 1
                sys.stdout.write("coherence: BAD <unparseable line>\n")
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
            else:
                # Dropping this silently was the first version's bug: a JSON array or scalar
                # on its own line vanished from both the report and the exit code.
                malformed += 1
                sys.stdout.write(f"coherence: BAD <non-object line: {type(parsed).__name__}>\n")
        results = check_run_coherence(rows)
        bad = [r for r in results if not r.ok]
        for r in results if not args.quiet else bad:
            flag = "BAD" if not r.ok else ("... " if r.incomplete else "OK ")
            sys.stdout.write(f"{flag} {r.agent} {r.stage} {r.slug} {r.run_id} passes={r.passes}\n")
            for problem in r.problems:
                sys.stdout.write(f"      -> {problem}\n")
            if r.incomplete:
                sys.stdout.write("      -> in flight (no terminal row yet) — not a defect\n")
        inflight = sum(1 for r in results if r.incomplete and r.ok)
        sys.stdout.write(
            f"coherence: {len(results) - len(bad)} ok ({inflight} in flight), "
            f"{len(bad)} incoherent, {malformed} malformed line(s)\n"
        )
        return 1 if bad or malformed else 0

    if args.command == "reconcile":
        from harness_maker.economics_source import load_turns

        project = Path(args.root).resolve()
        if not project.is_dir():
            # A typo'd root would otherwise discover nothing, find no ledger, and print a
            # confident `agrees=yes` — the same silent-zero shape the encoder fix removed.
            sys.stderr.write(f"[stage-agents] reconcile: no such directory: {project}\n")
            return 1
        ingestion = load_turns(project, days=None)
        groups = sidechain_turn_groups(ingestion.turns)
        path = ledger_path(resolve_base_root(project))
        rows_r: list[dict[str, Any]] = []
        malformed_r = 0
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    parsed_r = json.loads(line)
                except (ValueError, RecursionError):
                    # Counted and printed, never silently dropped: the `coherence` branch above
                    # already learned this — a dropped row lowers `dispatches`, and lowering it
                    # can only move the verdict TOWARD agreement, so silence here flatters the
                    # answer. `RecursionError` matches `economics_source`'s reader; the ledger
                    # is concurrently appended, so torn lines are expected, not hypothetical.
                    malformed_r += 1
                    continue
                if isinstance(parsed_r, dict):
                    rows_r.append(parsed_r)
                else:
                    malformed_r += 1
        result = reconcile_counts(rows_r, subagent_turn_groups=groups)
        sys.stdout.write(
            f"{project.name}: ledger_dispatches={result.ledger_dispatches} "
            f"sidechain_turn_groups={result.turn_groups} "
            f"(dirs_scanned={ingestion.diagnostics.dirs_scanned}, turns={len(ingestion.turns)}, "
            f"malformed_rows={malformed_r}) "
            f"agrees={'yes' if result.agrees else 'NO'}\n"
        )
        if result.reason:
            sys.stdout.write(f"      -> {result.reason}\n")
        if malformed_r:
            sys.stdout.write(
                f"      -> {malformed_r} malformed ledger line(s) excluded from the count\n"
            )
        # Diagnostic-only, and the exit code says which kind of outcome this was: 0 = agrees,
        # 2 = a disagreement (which can be an EXPECTED, permanent state — spoton has not run a
        # gated stage since its emit was rendered). `1` stays reserved for tool failure above,
        # so an operator or an `&&` chain can tell "the fleet disagrees" from "the tool broke".
        return 0 if result.agrees else 2

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
