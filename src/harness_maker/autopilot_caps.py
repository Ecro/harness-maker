"""Runaway caps + kill switch for autopilot chaining (ADR-007, P5).

A chained autopilot session accumulates every advanced stage into ONE growing turn
(P0 spike caveat), so step/time caps are load-bearing — a runaway chain is a single
long turn. ``evaluate_boundary`` is the pure predicate the P6 stage-terminal calls at
every boundary BEFORE invoking the next stage; the kill switch (marker removal) wins
over the caps so a user can always abort mid-chain. Token/cost budget is deferred.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
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


def next_stage(pipeline: Sequence[str], current: str) -> str | None:
    """The stage after ``current`` in ``pipeline``; None when ``current`` is last/unknown."""
    try:
        idx = list(pipeline).index(current)
    except ValueError:
        return None
    nxt = idx + 1
    return pipeline[nxt] if nxt < len(pipeline) else None


def _cmd_boundary(args: argparse.Namespace) -> int:
    """The deterministic boundary check the P6 auto-branch runs before advancing.

    Single entrypoint: resolves the live marker (kill switch when absent/foreign/stale),
    counts this session's prior ``advanced`` events as ``steps``, applies the caps, and
    on the proceed path records the advance it authorizes (so the next call's step count
    accrues) + reports the next pipeline stage. At the last stage it clears the marker
    (ADR-006 — final stage ends the session) and reports pipeline_complete.
    """
    root = Path(args.root)
    out: dict[str, object] = {
        "proceed": False,
        "halt_kind": None,
        "reason": "",
        "steps": 0,
        "next_stage": None,
        "pipeline_complete": False,
    }
    marker = autopilot.active_marker(root)
    if marker is None:
        out["halt_kind"] = "kill_switch"
        out["reason"] = "autopilot marker absent/foreign/stale — aborting chain at boundary"
        print(json.dumps(out))
        return 0
    steps = autopilot_ledger.count_events(root, "advanced", since=marker.created_at)
    out["steps"] = steps
    decision = evaluate_boundary(
        root, steps=steps, step_cap=args.step_cap, time_cap_min=args.time_cap_min
    )
    if not decision.proceed:
        out["halt_kind"] = decision.halt_kind
        out["reason"] = decision.reason
        # Only the two cap kinds are halted_cap-recordable (kill switch handled above).
        # Explicit `==` branches so mypy narrows HaltKind → CapKind for record_cap_halt.
        if decision.halt_kind == "step_cap":
            record_cap_halt(root, halt_kind="step_cap", steps=steps)
        elif decision.halt_kind == "time_cap":
            record_cap_halt(root, halt_kind="time_cap", steps=steps)
        print(json.dumps(out))
        return 0
    # marker.pipeline holds AtomicStage (str-enum) members; `in` / index use str-equality
    # so a plain stage name like "research" matches (str(member) would give the enum repr,
    # not the value — do NOT stringify).
    if args.current not in marker.pipeline:
        # Unknown `--current` (typo / stage outside the pipeline) is NOT completion —
        # preserve the marker + surface a distinct halt so a bad value can't silently kill
        # the session while falsely claiming success (REVIEW P2: Codex + 2 reviewers).
        out["halt_kind"] = "unknown_stage"
        out["reason"] = f"current stage {args.current!r} not in the pipeline — marker preserved"
        print(json.dumps(out))
        return 0
    nxt = next_stage(marker.pipeline, args.current)
    if nxt is None:
        # `current` IS the last stage → end the session (ADR-006).
        autopilot.clear(root)
        out["pipeline_complete"] = True
        out["reason"] = "pipeline complete — autopilot session finished"
        print(json.dumps(out))
        return 0
    autopilot_ledger.append_event(root, event="advanced", fields={"to": nxt})
    out["proceed"] = True
    out["next_stage"] = nxt
    out["steps"] = steps + 1
    out["reason"] = f"advancing to {nxt}"
    print(json.dumps(out))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """`boundary` subcommand — the prose auto-branch's deterministic gate (P6)."""
    parser = argparse.ArgumentParser(add_help=False)
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("boundary", add_help=False)
    b.add_argument("--root", default=".")
    b.add_argument("--current", required=True)
    b.add_argument("--step-cap", type=int, required=True, dest="step_cap")
    b.add_argument("--time-cap-min", type=int, required=True, dest="time_cap_min")
    # gate-blocked (P7): the auto-branch records this when a mandatory gate holds the chain
    # — distinct from a cap halt, so the ledger shows WHY the chain stopped.
    g = sub.add_parser("gate-blocked", add_help=False)
    g.add_argument("--root", default=".")
    g.add_argument("--stage", required=True)
    # parse_args (not parse_known_args) so a stray/misspelled flag errors loud rather than
    # being silently swallowed (REVIEW P3).
    args = parser.parse_args(argv)
    if args.cmd == "boundary":
        return _cmd_boundary(args)
    if args.cmd == "gate-blocked":
        autopilot_ledger.append_event(
            Path(args.root), event="gate_blocked", fields={"stage": args.stage}
        )
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main(argv) in tests
    sys.exit(main())
