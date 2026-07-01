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

from harness_maker import autopilot, autopilot_ledger, command_registry

HaltKind = Literal["kill_switch", "step_cap", "time_cap", "merge_gate", "unknown_stage"]
CapKind = Literal["step_cap", "time_cap"]

# Stages the chain must NEVER auto-ENTER — it hands off to the human before them. The
# wrapup squash-land/merge is a one-way door (ADR-002: "the chain ALWAYS stops at the
# wrapup merge/push"); auto-advancing INTO wrapup runs that land before any gate can stop
# it (REVIEW P1-1, user-chosen "stop before wrapup" fix). Reaching one of these as the
# NEXT stage stops the chain, records a gate_blocked event, and clears the marker.
_HUMAN_GATED_STAGES: frozenset[str] = frozenset({"wrapup"})


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
    step_cap: int | None,
    time_cap_min: int | None,
    now: datetime | None = None,
) -> BoundaryDecision:
    """Decide whether the chain may advance past this boundary (PURE — no side effects).

    Order is deliberate: the kill switch (marker removed / foreign / stale) is checked
    FIRST so a user `autopilot off` (or a crashed session's expired marker) aborts the
    chain regardless of cap state; then the step cap; then the time cap.

    PLAN-autopilot-config-surface ADR-002: a ``None`` cap is UNLIMITED — that check is
    skipped. The kill switch is unconditional, so a marker is still required to proceed;
    unlimited removes only the runaway backstop, never the user's abort (marker removal).
    """
    moment = now if now is not None else datetime.now(UTC)
    marker = autopilot.active_marker(project_root, now=moment)
    if marker is None:
        return BoundaryDecision(
            proceed=False,
            halt_kind="kill_switch",
            reason="autopilot marker absent/foreign/stale — aborting chain at boundary",
        )
    if step_cap is not None and steps >= step_cap:
        return BoundaryDecision(
            proceed=False,
            halt_kind="step_cap",
            reason=f"step cap reached ({steps}/{step_cap})",
        )
    if time_cap_min is not None:
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
                reason=f"time cap reached ({elapsed_min:.1f}/{time_cap_min} min)",
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
    # Resolve cwd→base ONCE so the marker (active_marker) AND the ledger ops
    # (count_events / append_event / record_cap_halt / clear) below share one root —
    # otherwise the marker resolves to base while 'advanced' events land in the
    # worktree ledger, splitting the step count and breaking the smoke-check (REVIEW P2).
    root = autopilot.resolve_marker_root(Path(args.root))
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
    # Unknown `--current` (typo / stage outside the pipeline) is checked FIRST — BEFORE the
    # caps — so a bad value can't trigger the marker-clearing cap path and silently kill the
    # session while falsely claiming a cap halt (REVIEW P3). Marker preserved; the user fixes
    # the typo and re-runs (the cap still applies on the corrected call).
    # marker.pipeline holds AtomicStage (str-enum) members; `in` uses str-equality so a plain
    # stage name like "research" matches (str(member) gives the enum repr — do NOT stringify).
    if args.current not in marker.pipeline:
        out["halt_kind"] = "unknown_stage"
        out["reason"] = f"current stage {args.current!r} not in the pipeline — marker preserved"
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
        # P2-6 / P3: a runaway cap is a TERMINAL halt. Clear the marker so the session
        # ends cleanly — otherwise every later boundary call re-fires a duplicate
        # halted_cap event AND the Stop-hook backstop keeps blocking termination until
        # the 18h TTL. (kill_switch leaves no marker to clear.)
        if decision.halt_kind in ("step_cap", "time_cap"):
            autopilot.clear(root)
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
    if nxt in _HUMAN_GATED_STAGES:
        # P1-1 (user-chosen fix): NEVER auto-enter a human-gated stage. wrapup's Step 7.7
        # squash-land/merge is a one-way door, so the chain stops HERE (before wrapup),
        # records the gate, and clears the marker (Stop-hook stands down) — the human
        # then invokes `/hm:wrapup` deliberately. This is what enforces ADR-002's
        # "always stop at the wrapup merge/push" at the auto-advance layer.
        autopilot_ledger.append_event(root, event="gate_blocked", fields={"stage": nxt})
        autopilot.clear(root)
        out["halt_kind"] = "merge_gate"
        out["next_stage"] = nxt
        out["reason"] = (
            f"next stage {nxt!r} is human-gated (merge/push, ADR-002) — "
            "autopilot stopped; invoke it manually"
        )
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
    # Registry-driven misroute guard (PLAN-command-surface-registry ADR-004): redirects
    # the observed `autopilot_caps on` → `autopilot on` (and any cross-module misroute),
    # replacing the hand-written one-off that pointed at the now-deprecated Typer form.
    guard = command_registry.guard_or_none("autopilot_caps", argv)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(add_help=False)
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("boundary", add_help=False)
    b.add_argument("--root", default=".")
    b.add_argument("--current", required=True)
    # PLAN-autopilot-config-surface ADR-002: optional → absent flag = None = unlimited. The
    # stage template omits the flag when the config cap is null, so an unlimited harness simply
    # does not pass it; a finite harness passes the rendered integer.
    b.add_argument("--step-cap", type=int, default=None, dest="step_cap")
    b.add_argument("--time-cap-min", type=int, default=None, dest="time_cap_min")
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
        # P2-5: only record for a LIVE autopilot session. A spurious call with no active
        # marker (off / foreign / stale) must not pollute the ledger or the smoke-check
        # denominator with a phantom gate_blocked event.
        # Resolve cwd→base so the marker check and the ledger write target one root
        # (same asymmetry fix as _cmd_boundary — REVIEW P2).
        root = autopilot.resolve_marker_root(Path(args.root))
        if autopilot.active_marker(root) is None:
            return 0
        autopilot_ledger.append_event(root, event="gate_blocked", fields={"stage": args.stage})
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main(argv) in tests
    sys.exit(main())
