"""Auto-advance ledger — append-only JSONL (ADR-009, PLAN-human-bottleneck-auto-advance P5).

Minimal P5 surface: append one auto-advance event. P7 extends this with the
`/hm:health` smoke check + the `advanced` / `gate_blocked` call sites. The event
vocabulary is DISJOINT from ``iter_receipts.Verdict`` (`pass`/`fail`/`skipped`) by
design so a downstream reader can never confuse a Gate-0 verdict with an
auto-advance event (ADR-009).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, get_args

from harness_maker.iter_receipts import Verdict

DEFAULT_OBSERVABILITY_DIR = Path(".claude/observability")
LEDGER_FILENAME = "auto-advance.jsonl"

# ADR-009: disjoint from iter_receipts.Verdict {"pass", "fail", "skipped"}.
LedgerEvent = Literal["advanced", "gate_blocked", "halted_cap"]
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
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
