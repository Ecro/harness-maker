"""Stage-span ledger: forward, authoritative attribution of turns to /hm: stages."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from .second_opinion_invoke import resolve_base_root

SCHEMA_VERSION = 1

# A DISTINCT sentinel, deliberately not `economics.UNATTRIBUTED`: an emission from an
# un-re-rendered harness (no `--stage`) is a different fact from "no span claimed this
# turn", and collapsing the two hides the absent case instead of reporting it.
UNKNOWN_STAGE = "(unknown-stage)"


class TurnLike(Protocol):
    """Only what attribution needs — keeps this module free of the pricing model.

    Read-only members, deliberately: a mutable protocol attribute is INVARIANT, so
    `session_id: str | None` here would reject `TurnRecord.session_id: str` — the one
    type this protocol exists to accept.
    """

    @property
    def ts(self) -> datetime: ...

    @property
    def session_id(self) -> str | None: ...


class SpanEvent(BaseModel):
    """One ledger line. Fields are limited to what the emitting subprocess can observe.

    Notably absent: the turn uuid. A CLI invoked from a stage's shell line cannot know
    which assistant turn it belongs to, so requiring it would have made the record
    unpopulatable by its own producer.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: int
    event: Literal["start", "end"]
    stage: str
    cwd: str
    base_root: str
    git_branch: str | None = None
    task_slug: str | None = None
    ts: datetime
    session_id: str | None = None


class ReadDiagnostics(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    total_lines: int = 0
    malformed_lines: int = 0


class SpanAttribution(BaseModel):
    """Per-turn stage assignment plus the counters that keep every gap reportable."""

    model_config = ConfigDict(strict=True, extra="forbid")

    stages: tuple[str | None, ...] = ()
    capped_indices: tuple[int, ...] = ()
    ambiguous_session_join: int = 0
    unknown_stage_emissions: int = 0

    @property
    def capped_turn_count(self) -> int:
        return len(self.capped_indices)


class _Span(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    stage: str
    session_id: str | None
    start: datetime
    end: datetime | None = None
    attributed: int = 0
    capped: bool = False


# ------------------------------------------------------------------ ledger location


def ledger_path(cwd: Path) -> Path:
    """Always the BASE repo's ledger.

    A cwd-relative path inside `.worktrees/<slug>/` is gitignored churn that
    `task-land` deletes — the ledger would be empty for exactly the sessions it was
    built to measure. `resolve_base_root` is reused rather than re-derived: its
    docstring records a measured `--separate-git-dir` failure of the obvious
    implementations.
    """
    return resolve_base_root(cwd) / ".claude" / "observability" / "stage-spans.jsonl"


def emit_event(
    event: Literal["start", "end"],
    *,
    stage: str,
    cwd: Path,
    session_id: str | None = None,
    git_branch: str | None = None,
    task_slug: str | None = None,
    now: datetime | None = None,
) -> Path:
    """Append one event. Atomic per `telemetry.py`'s O_APPEND + single-write pattern."""
    base = resolve_base_root(cwd)
    record = SpanEvent(
        schema_version=SCHEMA_VERSION,
        event=event,
        stage=stage,
        cwd=str(Path(cwd).resolve()),
        base_root=str(base),
        git_branch=git_branch,
        task_slug=task_slug,
        ts=now or datetime.now(UTC),
        session_id=session_id or None,
    )
    path = base / ".claude" / "observability" / "stage-spans.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record.model_dump(mode="json")) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
    return path


def read_events(path: Path) -> tuple[list[SpanEvent], ReadDiagnostics]:
    """Absent ledger → empty, never an error. A partial trailing line is counted."""
    diag = ReadDiagnostics()
    if not path.is_file():
        return [], diag
    out: list[SpanEvent] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        diag.total_lines += 1
        try:
            # JSON validation mode, NOT model_validate(json.loads(...)): under
            # strict=True the Python-mode validator rejects an ISO string for a
            # datetime field, so every well-formed line would count as malformed.
            out.append(SpanEvent.model_validate_json(raw))
        except Exception:
            diag.malformed_lines += 1
    return out, diag


# ------------------------------------------------------------------ attribution


def _build_spans(events: Sequence[SpanEvent]) -> tuple[list[_Span], int]:
    """Chain start/end events into spans, **one open span per session**.

    The ledger is SHARED across concurrent sessions. A single global `current` — the
    first implementation — made any session's `start` close whatever span happened to
    be open, so session A's span ended the moment session B began one; A's Stop hook
    then declined to write its own `end` (it is session-scoped), leaving A's span
    permanently short. With `HM_SESSION_ID` absent (a documented WSL2 failure) B's span
    carries `session_id=None`, `_match` reports it degraded, and B's stage claims A's
    turns outright. Concurrent sessions are a supported workflow here and adjacent
    machinery has already had three contamination incidents (review F-02).

    Session-less events chain among themselves under the `None` key: they cannot be
    told apart, which is precisely what `ambiguous_session_join` reports.
    """
    unknown = 0
    spans: list[_Span] = []
    open_by_session: dict[str | None, _Span] = {}
    for ev in sorted(events, key=lambda e: e.ts):
        stage = ev.stage.strip()
        if not stage:
            stage = UNKNOWN_STAGE
            unknown += 1
        key = ev.session_id
        current = open_by_session.get(key)
        if ev.event == "start":
            if current is not None:
                current.end = ev.ts  # closed by this session's next start
                spans.append(current)
            open_by_session[key] = _Span(stage=stage, session_id=key, start=ev.ts)
        elif current is not None:
            current.end = ev.ts
            spans.append(current)
            del open_by_session[key]
        # An `end` with no matching open span in ITS session is dropped, not applied to
        # a neighbour's: `span-end` is already session-scoped on the write side, so a
        # stray end here means the start was lost, and closing someone else's span on
        # it is the very cross-session truncation this function exists to prevent.
    spans.extend(open_by_session.values())  # still open at session end
    return spans, unknown


def _match(span: _Span, turn: TurnLike) -> tuple[bool, bool]:
    """(in_window, degraded). Degraded = the span carries no session id to join on."""
    if turn.ts < span.start:
        return False, False
    if span.end is not None and turn.ts > span.end:
        return False, False
    if span.session_id is None:
        return True, True
    return span.session_id == turn.session_id, False


def attribute_turns(
    turns: Sequence[TurnLike],
    events: Sequence[SpanEvent],
    *,
    max_turns: int,
    max_min: float,
) -> SpanAttribution:
    """Assign each turn to the span containing it, bounded by both caps.

    Caps are independent rejections and terminal: once either fires the span is
    closed for good, so a late `end` or a later `start` cannot extend it. Turns
    before the first start are never back-filled onto a neighbouring stage.
    """
    spans, unknown = _build_spans(events)
    stages: list[str | None] = [None] * len(turns)
    capped: list[int] = []
    ambiguous = 0

    for idx, turn in enumerate(turns):
        # Later spans win ties: a turn at exactly the next start's ts belongs to the
        # span that just opened, not the one it closed.
        #
        # Two passes, exact-session first (review R2-06): `_match` accepts ANY turn
        # inside a session-less span, so a single-pass scan let an unjoinable span
        # outrank an exact match purely on list order — the outcome then depended on
        # which session emitted first, and a peer's turns were claimed outright. That is
        # the harm the per-session partition exists to prevent, so it must not survive
        # in the selection step.
        chosen: _Span | None = None
        degraded = False
        for exact_only in (True, False):
            for span in reversed(spans):
                if exact_only and span.session_id is None:
                    continue
                ok, deg = _match(span, turn)
                if ok:
                    chosen, degraded = span, deg
                    break
            if chosen is not None:
                break
        if chosen is None:
            continue
        if chosen.capped:
            capped.append(idx)
            continue
        if chosen.attributed >= max_turns:
            chosen.capped = True
            capped.append(idx)
            continue
        if (turn.ts - chosen.start).total_seconds() > max_min * 60.0:
            chosen.capped = True
            capped.append(idx)
            continue
        chosen.attributed += 1
        stages[idx] = chosen.stage
        if degraded:
            ambiguous += 1

    return SpanAttribution(
        stages=tuple(stages),
        capped_indices=tuple(capped),
        ambiguous_session_join=ambiguous,
        unknown_stage_emissions=unknown,
    )
