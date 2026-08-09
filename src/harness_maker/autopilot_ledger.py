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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, get_args

from harness_maker import command_registry
from harness_maker.iter_receipts import Verdict
from harness_maker.models import ARMED_LEVELS, OPERATIONAL_LEVELS

DEFAULT_OBSERVABILITY_DIR = Path(".claude/observability")
LEDGER_FILENAME = "auto-advance.jsonl"

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
    pending: list[dict[str, Any]] = []
    for row in rows:
        if row.get("to") != to:
            continue
        event = row.get("event")
        if event == "advance_authorized":
            # Collapse consecutive authorizations with no entry between them. A re-run
            # boundary (a corrected `--slug`, a retried stage) issues a second
            # authorization for the same stage; banking both would let ONE real entry be
            # followed by a second confirmable slot, so a later unrelated entry could
            # consume it and the step cap would count work that never happened.
            if not pending:
                pending.append(row)
        elif event == "advance_entered" and pending:
            pending.pop(0)
    return pending[0] if pending else None


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
    degraded = armed and count == 0
    if degraded:
        reason = (
            f"autonomy.level={yaml_level!r} but the auto-advance ledger has 0 entries — "
            "autopilot is configured yet never fired (possible silent degradation)"
        )
    elif not armed:
        reason = f"autonomy not armed (level={yaml_level!r}) — no auto-advance expected"
    else:
        reason = f"autonomy.level={yaml_level!r}, {count} ledger entr{'y' if count == 1 else 'ies'}"
    return {"degraded": degraded, "level": yaml_level, "entry_count": count, "reason": reason}


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
    args = parser.parse_args(argv)
    if args.cmd == "smoke":
        print(json.dumps(smoke_check(Path(args.root), yaml_level=args.level)))
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main(argv) in tests
    sys.exit(main())
