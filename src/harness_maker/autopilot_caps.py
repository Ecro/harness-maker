"""Runaway caps + kill switch for autopilot chaining (ADR-007, P5).

A chained autopilot session accumulates every advanced stage into ONE growing turn
(P0 spike caveat), so step/time caps are load-bearing — a runaway chain is a single
long turn. ``evaluate_boundary`` is the pure predicate the P6 stage-terminal calls at
every boundary BEFORE invoking the next stage; the kill switch (marker removal) wins
over the caps so a user can always abort mid-chain. Token/cost budget is deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from harness_maker import autopilot, autopilot_ledger

HaltKind = Literal["kill_switch", "step_cap", "time_cap"]
CapKind = Literal["step_cap", "time_cap"]


@dataclass(frozen=True)
class BoundaryDecision:
    """Outcome of a boundary check. ``proceed`` False ⇒ ``halt_kind`` is set."""

    proceed: bool
    halt_kind: HaltKind | None
    reason: str


def evaluate_boundary(
    project_root: Path,
    *,
    steps: int,
    step_cap: int,
    time_cap_min: int,
    now: datetime | None = None,
) -> BoundaryDecision:
    """Decide whether the chain may advance past this boundary (PURE — no side effects).

    Order is deliberate: the kill switch (marker removed / foreign / stale) is checked
    FIRST so a user `autopilot off` (or a crashed session's expired marker) aborts the
    chain regardless of cap state; then the step cap; then the time cap.
    """
    moment = now if now is not None else datetime.now(UTC)
    marker = autopilot.active_marker(project_root, now=moment)
    if marker is None:
        return BoundaryDecision(
            proceed=False,
            halt_kind="kill_switch",
            reason="autopilot marker absent/foreign/stale — aborting chain at boundary",
        )
    if steps >= step_cap:
        return BoundaryDecision(
            proceed=False,
            halt_kind="step_cap",
            reason=f"step cap reached ({steps}/{step_cap})",
        )
    # active_marker already validated created_at is parseable + within the TTL, so this
    # parse cannot raise here; re-parsed (not threaded out of active_marker) to keep the
    # marker module's return surface minimal.
    created = datetime.fromisoformat(marker.created_at)
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    elapsed_min = (moment - created).total_seconds() / 60.0
    if elapsed_min >= time_cap_min:
        return BoundaryDecision(
            proceed=False,
            halt_kind="time_cap",
            reason=f"time cap reached ({elapsed_min:.0f}/{time_cap_min} min)",
        )
    return BoundaryDecision(proceed=True, halt_kind=None, reason="")


def record_cap_halt(
    project_root: Path,
    *,
    halt_kind: CapKind,
    steps: int,
    now: datetime | None = None,
    observability_dir: Path | None = None,
) -> None:
    """Append a ``halted_cap`` ledger event when a runaway cap fired.

    Only the two cap kinds are recordable: a ``kill_switch`` abort is user-initiated
    (marker removal), NOT a runaway cap, so it is rejected here (and never emits a
    ``halted_cap`` event — ADR-009 reserves that event for cap fires).
    """
    if halt_kind not in ("step_cap", "time_cap"):
        raise ValueError(
            f"record_cap_halt records only cap halts; got {halt_kind!r} "
            "(kill_switch is user-initiated, not a halted_cap event)"
        )
    # Normalize a naive `now` to UTC so the ledger ts is never tz-ambiguous (a naive
    # datetime would write a bare ISO string while the auto path emits the Z form — REVIEW P3).
    if isinstance(now, datetime):
        ts: str | None = (now if now.tzinfo is not None else now.replace(tzinfo=UTC)).isoformat()
    else:
        ts = None
    autopilot_ledger.append_event(
        project_root,
        event="halted_cap",
        fields={"halt_kind": halt_kind, "steps": steps},
        now=ts,
        observability_dir=observability_dir,
    )
