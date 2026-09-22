"""Auto-advance ledger — append-only JSONL (ADR-009, PLAN-human-bottleneck-auto-advance P5).

Minimal P5 surface: append one auto-advance event. P7 extends this with the
`/hm:health` smoke check + the `advanced` / `gate_blocked` call sites. The event
vocabulary is DISJOINT from ``iter_receipts.Verdict`` (`pass`/`fail`/`skipped`) by
design so a downstream reader can never confuse a Gate-0 verdict with an
auto-advance event (ADR-009).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, get_args

from harness_maker import command_registry, ledger_exclusions, verifier_discrimination
from harness_maker.io_utils import atomic_write
from harness_maker.iter_receipts import Verdict
from harness_maker.models import ARMED_LEVELS, OPERATIONAL_LEVELS

DEFAULT_OBSERVABILITY_DIR = Path(".claude/observability")
LEDGER_FILENAME = "auto-advance.jsonl"

#: Where the clone-surviving roll-up lands (ADR-002 of PLAN-token-efficiency-autopilot-ux-speed).
#:
#: The prefix is load-bearing, not cosmetic. `.gitignore` excludes `work-docs/*` and re-includes
#: only the prefixes in `worktree.DELIVERABLE_PREFIXES`, a set with three consumers that a test
#: asserts are equal — so a name outside it is silently gitignored and never lands, and a name
#: added to the gitignore negation but NOT to that set becomes tracked non-deliverable dirt that
#: blocks every `worktree create`. `BASELINE-` is already in the set, so nothing else moves.
#:
#: It is also spelled with the literal `work-docs/` rather than the templates' neighbouring
#: `{{ config.work_docs.dir }}`: the writer below hardcodes this constant, so a configured
#: directory would stage a path the writer never writes. The non-default `work_docs.dir` case is
#: an accepted limitation of the SPEC, inherited from both worktree dirt-filters.
ROLLUP_RELPATH = "work-docs/BASELINE-ledger-rollup.md"

# ADR-009: disjoint from iter_receipts.Verdict {"pass", "fail", "skipped"}.
#
# `advanced` is LEGACY and is never written again (PLAN-autopilot-advance-noop ADR-004).
# It stayed in the vocabulary so historical rows remain readable. It was replaced because
# the boundary CLI appended it BEFORE the model acted, so the ledger recorded every
# authorization as a success — which is precisely why "announces the next stage but never
# runs it" survived undetected. `advance_authorized` is the permission; `advance_entered`
# is the proof the stage actually started.
LedgerEvent = Literal[
    "advanced",
    "advance_authorized",
    "advance_entered",
    "gate_blocked",
    # The auto_full counterpart of `gate_blocked`: a human judgment point the level cleared
    # instead of stopping at. Without it an auto_full pass over the plan interview is
    # byte-identical on the ledger to an ordinary auto_safe advance, so no audit can count
    # how many human decisions the widest level skipped.
    "gate_auto_answered",
    "halted_cap",
    # One row per ACCEPTED objective proposal, written by `hm world objective new
    # --from-proposal` (PLAN-objective-gap-proposal ADR-003/004). Adoption is read as rows ÷
    # `proposed`+approved records; a declined-everything turn leaves no row by design.
    "objective_proposed",
]
# DERIVED from LedgerEvent (not a hand-maintained copy) so the typed signature and the
# runtime guard cannot drift apart (REVIEW P2). The two module-level asserts make
# ADR-009 a structural, import-time invariant — not a test-only guarantee.
EVENTS: frozenset[str] = frozenset(get_args(LedgerEvent))
assert EVENTS.isdisjoint(get_args(Verdict)), (
    "ADR-009: auto-advance ledger EVENTS must be disjoint from iter_receipts.Verdict"
)


def ledger_path(project_root: Path, observability_dir: Path | None = None) -> Path:
    """Single source for the ledger location.

    An ABSOLUTE ``observability_dir`` must stay within ``project_root`` — the
    containment guard mirrors ``codex_ledger.emit`` (REVIEW P1): without it a
    config-influenced or future absolute call-site could write the ledger anywhere on
    disk, outside the tree.
    """
    base = observability_dir if observability_dir is not None else DEFAULT_OBSERVABILITY_DIR
    resolved_root = project_root.resolve()
    if base.is_absolute():
        resolved_base = base.resolve()
        if not resolved_base.is_relative_to(resolved_root):
            raise ValueError(
                f"observability_dir {resolved_base} escapes project_root {resolved_root}"
            )
        base = resolved_base
    else:
        base = resolved_root / base
    return base / LEDGER_FILENAME


def _utc_now_iso() -> str:
    # Microsecond + offset isoformat — MUST match the marker's created_at resolution
    # (autopilot.write uses datetime.now(UTC).isoformat()). A second-truncated ts would
    # sort BEFORE a same-second marker.created_at, so count_events' `ts >= since` filter
    # would DROP a same-second `advanced` event → step count under-counts → the step cap
    # never fires (P8 e2e caught this).
    return datetime.now(tz=UTC).isoformat()


def _append_atomic_line(path: Path, line: str) -> None:
    """Append one line via O_APPEND — kernel-atomic for writes <= PIPE_BUF (4096).

    Mirrors ``codex_ledger._append_atomic_line``: concurrent writers (autoloop +
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


def append_event(
    project_root: Path,
    *,
    event: LedgerEvent,
    fields: dict[str, Any] | None = None,
    now: str | None = None,
    observability_dir: Path | None = None,
) -> None:
    """Append one event line. Rejects any event outside ``EVENTS`` (ADR-009).

    The membership check is the load-bearing guard: ``EVENTS`` is disjoint from
    ``iter_receipts.Verdict``, so passing ``"pass"``/``"fail"``/``"skipped"`` (or any
    other non-event string) raises rather than silently polluting the ledger.
    """
    if event not in EVENTS:
        raise ValueError(
            f"auto-advance ledger event {event!r} not in {sorted(EVENTS)} "
            "(ADR-009: vocabulary is disjoint from iter_receipts.Verdict)"
        )
    # `fields` is merged FIRST, then the authoritative ts + event overwrite it — so a
    # caller's fields={"event": "pass"} can never smuggle an iter_receipts.Verdict
    # literal past the membership guard onto disk (ADR-009 bypass; Codex review P1).
    record: dict[str, Any] = dict(fields) if fields else {}
    record["ts"] = now if now is not None else _utc_now_iso()
    record["event"] = event
    _append_atomic_line(
        ledger_path(project_root, observability_dir), json.dumps(record, ensure_ascii=False)
    )


def _parse_iso(value: str) -> datetime | None:
    """Parse an ISO-8601 ts to an aware UTC datetime; None when unparseable."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def count_events(
    project_root: Path,
    event: str,
    *,
    since: str | None = None,
    observability_dir: Path | None = None,
) -> int:
    """Count ledger events of one type, optionally only those with ``ts >= since``.

    The `since` filter parses BOTH sides to aware datetimes (not a lexicographic string
    compare). The marker's `created_at` and the live ledger ts are now both `isoformat`
    (`...SS.ffffff+00:00`, P8 fix to `_utc_now_iso`), but a byte compare is still wrong:
    legacy rows on disk may carry the old `...SSZ` form, and `_parse_iso` normalizes the `Z`
    so mixed-format ledgers still compare correctly. The P6 boundary CLI passes the marker's
    `created_at` to scope the `advanced` count to the current session. Fail-safe: a missing
    ledger / unparseable line never raises (counts as zero); a row with a missing/unparseable
    ts is counted IN-WINDOW (block-biased toward firing the step cap — see P2-4 below).
    """
    path = ledger_path(project_root, observability_dir)
    if not path.is_file():
        return 0
    since_dt = _parse_iso(since) if since is not None else None
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or record.get("event") != event:
            continue
        if since_dt is not None:
            ts = record.get("ts")
            ts_dt = _parse_iso(ts) if isinstance(ts, str) else None
            # P2-4: only skip rows PROVABLY older than `since`. A missing/garbage ts is
            # counted (in-window) — dropping it would UNDER-count `advanced` events and
            # delay the runaway step cap (the wrong fail-safe direction; the cap must be
            # block-biased toward firing, not toward running longer).
            if ts_dt is not None and ts_dt < since_dt:
                continue
        total += 1
    return total


def _rows_in_window(
    project_root: Path,
    *,
    since: str | None,
    observability_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Every parseable ledger row with ``ts >= since``, in append (chronological) order.

    Same fail-safe posture as ``count_events``: a missing ledger or an unparseable line is
    skipped rather than raised, and a row with a missing/garbage ts is kept IN-window
    (block-biased — dropping it would under-count and delay the runaway cap).
    """
    path = ledger_path(project_root, observability_dir)
    if not path.is_file():
        return []
    since_dt = _parse_iso(since) if since is not None else None
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if since_dt is not None:
            ts = record.get("ts")
            ts_dt = _parse_iso(ts) if isinstance(ts, str) else None
            if ts_dt is not None and ts_dt < since_dt:
                continue
        rows.append(record)
    return rows


def find_unconfirmed_authorization(
    project_root: Path,
    *,
    to: str,
    since: str | None,
    observability_dir: Path | None = None,
) -> dict[str, Any] | None:
    """The earliest ``advance_authorized(to=…)`` in the window with no matching entry yet.

    Greedy in-order pairing (ADR-005). A stage can be authorized and entered more than
    once per session (review→execute→review), so pairing is oldest-authorization to
    oldest-entry rather than by identity — no ids are introduced. An entry can only
    confirm an authorization that PRECEDES it, which is what stops a stale entry from
    swallowing a fresh authorization.
    """
    rows = _rows_in_window(project_root, since=since, observability_dir=observability_dir)
    # Pair in APPEND order, in a single pass. The ledger is O_APPEND, so file order IS
    # write order — an authoritative ordering that needs no timestamps. The first draft
    # split the two event kinds apart and reconstructed order from `ts`, which made the
    # pairing hostage to the clock: a rollback could let an entry recorded BEFORE an
    # authorization pair with it, and a missing/garbage `ts` skipped the ordering check
    # entirely. Timestamps are for the window filter and `elapsed_s`, nothing else.
    return next(iter(_pending_authorizations(rows, to=to, collapse=True)), None)


def _pending_authorizations(
    rows: list[dict[str, Any]], *, to: str, collapse: bool
) -> list[dict[str, Any]]:
    """The greedy in-order pairing, once, with the collapse as a POLICY the caller chooses.

    `collapse=True` banks at most one outstanding authorization per stage. That is correct for a
    SESSION window (`_confirm_entry`): a re-run boundary — a corrected `--slug`, a retried stage —
    issues a second authorization for the same stage, and banking both would leave a second
    confirmable slot that a later unrelated entry could consume, so the step cap would count work
    that never happened.

    It is WRONG for a lifetime window, which is what `dangling_authorizations` asks for (review
    finding P1-2). Two authorizations for the same stage in different sessions are two independent
    events; collapsing them means any later successful advance to that stage erases an earlier
    dangling one, and at most one dangling row per stage can ever be reported. A project that
    announced-but-never-ran `plan` twelve times, each followed eventually by a real `plan`, printed
    `- none` — the "table of zeros reads as a clean bill of health" outcome `render_rollup` exists
    to refuse.

    The pairing itself stays in ONE place: a second copy would be a future contradiction with no
    detector, which is why the fix is a parameter rather than a sibling implementation.
    """
    pending: list[dict[str, Any]] = []
    for row in rows:
        if row.get("to") != to:
            continue
        event = row.get("event")
        if event == "advance_authorized":
            if collapse and pending:
                continue
            pending.append(row)
        elif event == "advance_entered" and pending:
            pending.pop(0)
    return pending


def dangling_authorizations(
    project_root: Path,
    *,
    since: str | None = None,
    observability_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Every stage whose authorization no entry confirmed — the reader ADR-004/005 never had.

    `find_unconfirmed_authorization` already computes this, per target stage, and had exactly one
    caller (`_confirm_entry`), so the "announced the next stage, never ran it" defect was recorded
    on disk and read by nothing. This adds only the enumeration: the greedy in-order pairing is
    NOT reimplemented here, because a second copy of it is a future contradiction with no detector.
    """
    rows = _rows_in_window(project_root, since=since, observability_dir=observability_dir)
    targets = sorted({str(row["to"]) for row in rows if row.get("to")})
    found: list[dict[str, Any]] = []
    for target in targets:
        # `collapse=False`: every unconfirmed authorization, not just the earliest per stage. See
        # `_pending_authorizations` — the collapse is a session-window policy and this is a lifetime
        # enumeration. Reads the SAME `rows` the target set came from, so there is one window and
        # one directory rather than a re-read that could resolve differently.
        found.extend(_pending_authorizations(rows, to=target, collapse=False))
    return found


@dataclass(frozen=True)
class Rollup:
    """One snapshot of what the ledgers hold, in a form that survives a clone.

    Deliberately carries NO timestamp. A `BASELINE-` deliverable naturally invites one, and that
    is exactly what would break the per-axis differential guarding this render: two renders taken
    microseconds apart would differ for a reason having nothing to do with the aggregate, so the
    assertion would pass vacuously. git already records when the file changed, which is the
    provenance ADR-002 relies on.
    """

    by_model: dict[str, dict[str, Any]]
    by_stage: dict[str, int]
    total: int
    exclusions: dict[str, Any]
    dangling: list[dict[str, Any]]


def rollup(project_root: Path, *, observability_dir: Path | None = None) -> Rollup:
    """Aggregate the ledgers by COMPOSING the shipped readers, never re-deriving the formula.

    ADR-010. Hand-aggregating this ledger family has shipped a 30x error (61.3% reported against
    the reader's 2.15%, three times, from a missing exclusions file) and a 10.3%-vs-20.7% error
    (from a `skipped/total` formula that lost a model's whole loss into `failed` rows). So the
    loss arithmetic, the `finding_ref` invocation/disposition split, the `health` exclusion and
    the exclusions filter all stay where they already are and are called, not copied.

    `by_stage` is built by calling `analyse` once per stage rather than by filtering rows here —
    that way the two filters it applies have exactly one definition, and the literals `"n/a"` and
    `"health"` appear nowhere in this module.
    """
    # Resolve against `project_root`, matching `ledger_path`. The first draft used a bare
    # `Path(DEFAULT_OBSERVABILITY_DIR)`, which silently read the CWD instead — invisible to every
    # test here because they all pass `observability_dir` explicitly, and the absent-case class
    # CLAUDE.md records at count:8. Caught by running the CLI, not by reading.
    # Normalised ONCE, and made absolute: `load_exclusions`/`read_rows` below resolve a relative
    # path against the CWD while `ledger_path` resolves it against `project_root`, so a relative
    # `observability_dir` made the second-opinion half and the auto-advance half read DIFFERENT
    # directories (review finding P2-4). Unreachable from today's callers — which is exactly the
    # shape of the CWD defect this function already carries a comment about.
    obs = observability_dir if observability_dir is not None else Path(DEFAULT_OBSERVABILITY_DIR)
    if not obs.is_absolute():
        obs = project_root / obs
    exclusions = verifier_discrimination.load_exclusions(obs)
    rows = verifier_discrimination.read_rows(obs / verifier_discrimination.DEFAULT_LEDGER.name)
    kept = [row for row in rows if not ledger_exclusions.is_excluded(row, exclusions)]

    payload = verifier_discrimination.to_payload(
        verifier_discrimination.analyse(kept), exclusions, dropped_n=len(rows) - len(kept)
    )
    by_model: dict[str, dict[str, Any]] = payload["models"]

    by_stage: dict[str, int] = {}
    for stage in sorted({str(row.get("stage")) for row in kept if row.get("stage") is not None}):
        subset = [row for row in kept if str(row.get("stage")) == stage]
        calls = sum(s.calls for s in verifier_discrimination.analyse(subset).values())
        if calls:
            by_stage[stage] = calls

    return Rollup(
        by_model=by_model,
        by_stage=by_stage,
        total=sum(int(m["calls"]) for m in by_model.values()),
        exclusions=payload["exclusions"],
        dangling=dangling_authorizations(project_root, observability_dir=observability_dir),
    )


def render_rollup(snapshot: Rollup) -> str:
    """Markdown for `ROLLUP_RELPATH`. Every aggregate axis reaches the text, or the gate fails.

    The absence case says so in prose rather than printing zeros: a table of zeros reads as a
    clean bill of health, and the shipped reader this composes already answers absence with
    "this is not a clean bill of health; it is an absence of evidence".
    """
    lines = ["# Ledger roll-up", ""]
    if not snapshot.by_model:
        lines += [
            f"No rows. {verifier_discrimination.ABSENCE_NOTICE} —",
            "the ledgers are gitignored, so a fresh clone starts empty and only a run fills them.",
            "",
        ]
    else:
        lines += ["## Per model", "", "| model | calls | invoked | skipped | failed | loss_rate |"]
        lines.append("|---|---|---|---|---|---|")
        for name, stats in sorted(snapshot.by_model.items()):
            lines.append(
                f"| {name} | {stats['calls']} | {stats['invoked']} | {stats['skipped']} "
                f"| {stats['failed']} | {stats['loss_rate']} |"
            )
        lines += ["", "## Per stage", "", "| stage | calls |", "|---|---|"]
        for stage, calls in sorted(snapshot.by_stage.items()):
            lines.append(f"| {stage} | {calls} |")
        lines += ["", f"Invocation rows counted: {snapshot.total}.", ""]

    lines += [
        "## Exclusions applied",
        "",
        f"Rows dropped: {snapshot.exclusions['rows_dropped']}.",
        "",
    ]
    for entry in snapshot.exclusions["applied"]:
        lines.append(f"- `{entry['key']}={entry['value']}` — {entry['reason']}")
    if not snapshot.exclusions["applied"]:
        lines.append("- none")

    lines += ["", "## Dangling authorizations", ""]
    if snapshot.dangling:
        for row in snapshot.dangling:
            lines.append(f"- authorized to `{row.get('to')}` with no confirming entry")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def rows_root(project_root: Path) -> Path:
    """Where the ROWS are, which is not where the deliverable goes.

    Every writer in this ledger family files at the **base** repo root on purpose: a worktree's
    `.claude/observability/` is gitignored and vanishes at `task-land`, and that row-loss has
    already been paid for once (`codex_ledger.main()`'s `project_root=Path.cwd()`). The reader has
    to follow the writer, and it did not: invoked from inside `.worktrees/<slug>/`, the first real
    run read the worktree's empty directory and wrote `No rows.` into a document `/hm:wrapup`
    commits, while the base held `second-opinion.jsonl`, `auto-advance.jsonl`, `stage-agents.jsonl`
    and `stage-spans.jsonl`. A committed deliverable asserting an absence the evidence contradicts
    is the exact defect class this unit exists to remove.

    Returns the base ROOT rather than its observability dir, because `count_entries`' guard rejects
    an `observability_dir` that escapes `project_root` — correctly, and that rail stays. So the read
    is rooted at base and only the write destination moves.

    `resolve_base_root` is reused, not re-implemented: it is the shipped resolver and it already
    handles the `--separate-git-dir` layout that defeated an earlier hand-rolled attempt. Without
    `git` it falls back to the given root and never raises; the roll-up then reports whatever that
    root holds, which is the honest answer outside a repo.
    """
    from harness_maker.second_opinion_invoke import resolve_base_root

    return resolve_base_root(project_root)


def write_rollup(
    project_root: Path,
    *,
    observability_dir: Path | None = None,
    destination_root: Path | None = None,
) -> Path:
    """Render the snapshot to `ROLLUP_RELPATH` and return the path written.

    This exists because `rollup` + `render_rollup` without a caller is the defect AC-014 names —
    "a correct helper wired to nothing is the defect, not the fix" — and AC-001's committed-path
    conjunct can only ever be true if something writes the file. `atomic_write`, not a plain
    `open(path, "w")`: a torn deliverable is worse than an absent one, and the project forbids the
    plain form.
    """
    # `destination_root` defaults to `project_root`, so every existing caller is unchanged. It
    # exists because the read root and the write root genuinely differ inside a task worktree: rows
    # at base, deliverable where `/hm:wrapup` will commit it.
    destination = (
        destination_root if destination_root is not None else project_root
    ) / ROLLUP_RELPATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(
        destination, render_rollup(rollup(project_root, observability_dir=observability_dir))
    )
    return destination


def count_entries(
    project_root: Path,
    *,
    since: str | None = None,
    observability_dir: Path | None = None,
) -> int:
    """Stages actually ENTERED in the window — the step-cap numerator (ADR-004).

    Legacy `advanced` rows are counted only while they PRECEDE the first new-vocabulary row.
    The new vocabulary is never written by old code and the legacy name is never written by
    new code, so that boundary is exactly the upgrade point inside a mixed window (a marker
    armed under the old code and still inside its 18h TTL when this ships).

    The two ways to get this wrong pull in opposite directions, and only one of them is
    safe. Dropping the legacy rows wholesale hands a partially-consumed session a FRESH
    step budget — the chain then runs longer than configured. Counting a pre-upgrade
    phantom (`advanced` written before the model acted, which is the defect this split
    exists to fix) alongside its re-done new-vocabulary pair over-counts one advance by
    one, so the cap fires one step early. The runaway cap must be block-biased toward
    firing — `count_events` states the same rule for its own missing-ts case — so the sum
    is correct and the wholesale drop is not.
    """
    rows = _rows_in_window(project_root, since=since, observability_dir=observability_dir)
    new_vocabulary = ("advance_entered", "advance_authorized")
    upgrade_point = len(rows)
    for idx, row in enumerate(rows):
        if row.get("event") in new_vocabulary:
            upgrade_point = idx
            break
    entered = sum(1 for r in rows if r.get("event") == "advance_entered")
    legacy_before_upgrade = sum(1 for r in rows[:upgrade_point] if r.get("event") == "advanced")
    return entered + legacy_before_upgrade


# The autonomy levels that actually arm auto-advance (gated = off; unknown = treated as
# off, matching autopilot.effective_level's clamp-unknown-to-gated fail-safe).
_ARMED_LEVELS: frozenset[str] = ARMED_LEVELS


def _total_entries(project_root: Path, observability_dir: Path | None = None) -> int:
    """Count ALL valid ledger entries (any event in EVENTS) — the smoke denominator."""
    return sum(count_events(project_root, ev, observability_dir=observability_dir) for ev in EVENTS)


def smoke_check(
    project_root: Path,
    *,
    yaml_level: str,
    observability_dir: Path | None = None,
    targets: Sequence[str] | None = None,
) -> dict[str, Any]:
    """`/hm:health` positive smoke (P7): autonomy ARMED in yaml but ZERO ledger entries
    → surface degradation (autopilot configured yet never fired — the H4 silent-degrade
    failure mode). Only the canonical armed levels count: `gated` AND any unknown/garbage
    level are treated as not-armed (mirrors `autopilot.effective_level`'s clamp-unknown-to-
    gated fail-safe — REVIEW P1, the CLAUDE.md absent-case = feature-black-hole guard), so a
    typo'd level can never raise a false 'never fired' alarm.

    Scope (P3): this reads ONLY the committed ``harness.yaml`` level. It deliberately does
    NOT consult a live `.hm-autopilot` marker — `/hm:health` runs as its own session and a
    marker from a *different* session is foreign anyway. A session that armed auto-advance
    purely via the start-answer marker (yaml still `gated`) is therefore out of scope here;
    its activity is visible directly in the ledger.
    """
    count = _total_entries(project_root, observability_dir)
    armed = yaml_level in _ARMED_LEVELS
    # Claude dispatches via Skill; Codex reads and executes the next local skill.
    # Unknown targets retain the historical applicable default; Cursor-only does
    # not have a native continuation procedure.
    applicable = targets is None or bool({"claude-code", "codex"}.intersection(targets))
    degraded = applicable and armed and count == 0
    if not applicable:
        reason = (
            f"targets={list(targets or [])} omit 'claude-code' and 'codex' — "
            "no native auto-advance procedure; an empty ledger is expected"
        )
    elif degraded:
        reason = (
            f"autonomy.level={yaml_level!r} but the auto-advance ledger has 0 entries — "
            "autopilot is configured yet never fired (possible silent degradation)"
        )
    elif not armed:
        reason = f"autonomy not armed (level={yaml_level!r}) — no auto-advance expected"
    else:
        reason = f"autonomy.level={yaml_level!r}, {count} ledger entr{'y' if count == 1 else 'ies'}"
    return {
        "degraded": degraded,
        "applicable": applicable,
        "level": yaml_level,
        "entry_count": count,
        "reason": reason,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """`smoke` subcommand — the /hm:health auto-advance degradation probe (P7)."""
    _guard = command_registry.guard_or_none("autopilot_ledger", argv)
    if _guard is not None:
        return _guard
    parser = argparse.ArgumentParser(add_help=False)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke", add_help=False)
    s.add_argument("--root", default=".")
    # choices so a misspelled level errors loud (REVIEW P2); smoke_check also clamps unknown.
    s.add_argument("--level", required=True, choices=OPERATIONAL_LEVELS)
    # `--targets` exists because the applicability rule it feeds had NO production caller: the
    # rendered `/hm:health` passed only `--root`/`--level`, so `targets=None` made `applicable` True
    # unconditionally, and the PERMANENT false alarm on a cursor-only harness — "configured yet
    # never fired" for a runtime that structurally cannot advance — shipped unchanged while a unit
    # test saw the fix (review finding P1-3). Comma-separated; empty = unknown = applicable.
    s.add_argument("--targets", default="")
    r = sub.add_parser("rollup", add_help=False)
    r.add_argument("--root", default=".")
    r.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "smoke":
        _targets = [x.strip() for x in str(args.targets).split(",") if x.strip()] or None
        print(json.dumps(smoke_check(Path(args.root), yaml_level=args.level, targets=_targets)))
        return 0
    if args.cmd == "rollup":
        root = Path(args.root)
        # READ from the base repo, WRITE into the tree the caller is standing in. The asymmetry is
        # the point: rows live at base (the writers put them there), the deliverable has to land
        # where `/hm:wrapup` will commit it. Explicit `observability_dir` rather than two roots in
        # the signature, so `rollup`'s contract ("everything under project_root") stays intact.
        read_root = rows_root(root)
        if args.write:
            print(str(write_rollup(read_root, destination_root=root)))
        else:
            print(render_rollup(rollup(read_root)), end="")
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main(argv) in tests
    sys.exit(main())
