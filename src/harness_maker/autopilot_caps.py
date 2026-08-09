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
from harness_maker.models import GATED_LEVEL

# `bad_slug` is emitted only by `_cmd_boundary` (a rejected `--slug`), never by
# `evaluate_boundary` — but it IS part of the JSON contract the stage prompt branches on,
# so it belongs in the declared vocabulary. `out` is typed `dict[str, object]`, so mypy
# would not have caught the divergence: exactly the enum-drift CLAUDE.md flags where a
# name-only parity test is invariant to the values.
HaltKind = Literal[
    "kill_switch",
    "step_cap",
    "time_cap",
    "merge_gate",
    "judgment_gate",
    "unknown_stage",
    "bad_slug",
]
CapKind = Literal["step_cap", "time_cap"]

# Stages the chain must NEVER auto-ENTER — it hands off to the human before them. The
# wrapup squash-land/merge is a one-way door (ADR-002: "the chain ALWAYS stops at the
# wrapup merge/push"); auto-advancing INTO wrapup runs that land before any gate can stop
# it (REVIEW P1-1, user-chosen "stop before wrapup" fix). Reaching one of these as the
# NEXT stage stops the chain, records a gate_blocked event, and clears the marker.
_HUMAN_GATED_STAGES: frozenset[str] = frozenset({"wrapup"})

# ADR-009. Keyed on the stage that JUST RAN and owns the judgment — never on the
# (source, next) pair. A user-customised `autonomy.pipeline` changes which stage follows
# plan or review while leaving the judgment exactly where it was, so pair-keying would
# silently stop gating for those users: the absent-case = feature black hole shape.
#
# `_HUMAN_GATED_STAGES` stays next-stage-keyed. It guards a one-way door (wrapup lands to
# main), so what matters there is what is about to be ENTERED, not what just finished.
_JUDGMENT_GATED_STAGES: frozenset[str] = frozenset({"plan", "review"})


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
    session_id: str | None = None,
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
    marker = autopilot.active_marker(project_root, now=moment, session_id=session_id)
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


def _confirm_entry(project_root: Path, *, stage: str, marker: autopilot.AutopilotMarker) -> bool:
    """Retro-confirm that ``stage`` was actually entered (ADR-005). True when a row landed.

    Nothing else can observe this. The stage itself does not know whether it was
    auto-entered or user-invoked, and adding a dedicated call to seven prompts would tax
    every manual run — so the stage's own boundary/gate-blocked call doubles as the proof
    it started. A stage that dies mid-body reaches neither call and is correctly never
    confirmed: that silence is the signal the ledger was missing.

    ``elapsed_s`` rides along instead of a hard auto-vs-manual cutoff, so the threshold
    stays a query answerable against every historical row rather than a constant baked in
    here (ADR-009).
    """
    pending = autopilot_ledger.find_unconfirmed_authorization(
        project_root, to=stage, since=marker.created_at
    )
    if pending is None:
        return False
    authorized_at = pending.get("ts")
    elapsed_s = 0.0
    if isinstance(authorized_at, str):
        parsed = autopilot_ledger._parse_iso(authorized_at)
        if parsed is not None:
            elapsed_s = max(0.0, (datetime.now(UTC) - parsed).total_seconds())
    autopilot_ledger.append_event(
        project_root,
        event="advance_entered",
        fields={"to": stage, "elapsed_s": round(elapsed_s, 3)},
    )
    return True


def _resolve_task_slug(
    project_root: Path,
    *,
    marker: autopilot.AutopilotMarker,
    flag_slug: str | None,
    stage: str,
    session_id: str | None = None,
) -> tuple[str | None, str | None]:
    """The slug to hand the next stage, plus where it came from (ADR-003).

    ``task_slug_source`` exists because the fallback must never be silent. This ADR
    rejects slug *inference* on the grounds that "silently advancing the wrong task is
    worse than not advancing" — and an unannounced inherited slug produces that same
    outcome when a user starts a second task inside one armed session. Naming the source
    lets the prompt say which slug it is about to use.
    """
    if flag_slug:
        # Gate on the boolean. `set_task_slug` refuses a slug outside the allowlist, and
        # returning it anyway would hand the rejected value to the very sinks the allowlist
        # exists to protect: the JSON's `task_slug` becomes the `Skill(hm:<next> <slug>)`
        # argument, and the next stage re-emits it into its own `--slug` shell line.
        if autopilot.set_task_slug(
            project_root, slug=flag_slug, stage=stage, session_id=session_id
        ):
            return flag_slug, "flag"
        # stderr, not logging: this module's CLI output is the JSON on stdout and callers do
        # not configure logging, so a logger call here would be invisible.
        print(f"[autopilot] --slug {flag_slug!r} failed validation", file=sys.stderr)
        # DISTINCT sources, and both halt the boundary (see `_cmd_boundary`). Reporting the
        # fall-through as plain "persisted" made the JSON byte-identical to the benign "no
        # flag was passed" case, so the prompt could not tell that the slug it asked for was
        # refused and a DIFFERENT task's slug substituted.
        if marker.task_slug:
            return marker.task_slug, "rejected-fallback"
        return None, "rejected"
    if marker.task_slug:
        return marker.task_slug, "persisted"
    return None, None


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
        "task_slug": None,
        "task_slug_source": None,
        # Present on every response so a consumer can branch on the value rather than on
        # the key existing — an absent key and a false one read the same in prose.
        "judgment_auto_answered": False,
        "judgment_directive": None,
    }
    marker = autopilot.active_marker(root, session_id=args.session_id)
    if marker is None:
        out["halt_kind"] = "kill_switch"
        out["reason"] = "autopilot marker absent/foreign/stale — aborting chain at boundary"
        print(json.dumps(out))
        return 0
    if marker.level == GATED_LEVEL:
        # `gated` means "never auto-advance", and nothing here used to check it: every other
        # branch reads the level only to decide HOW to advance. That was unreachable while
        # the picker rendered only for non-gated harnesses and armed with the committed
        # level — B4 made it reachable by offering `gated` as a pick and instructing "arm
        # with the PICKED level", i.e. on the default (`ask`) path. Fail closed, and do NOT
        # clear the marker: arming gated is how a session records "asked, declined", and
        # clearing it would make the picker ask again every stage.
        # `kill_switch` is the honest halt kind (the rendered prose glosses it as "autopilot
        # off/expired", which is what gated means), but the ROW matters: without it a session
        # that was offered autopilot and declined is indistinguishable on the ledger from one
        # where the marker expired, and `smoke_check` reads exactly these rows.
        autopilot_ledger.append_event(root, event="gate_blocked", fields={"stage": args.current})
        out["halt_kind"] = "kill_switch"
        out["reason"] = (
            "autopilot level is 'gated' — auto-advance is off for this session. "
            "Marker preserved (it records the declined offer)."
        )
        print(json.dumps(out))
        return 0
    # AFTER the marker check, BEFORE the caps (ADR-005 placement). Running it first would
    # jump the P2-5 invariant those early returns carry — a call with no live marker
    # (autopilot off / foreign / stale) must append NOTHING, or every manual run pollutes
    # the smoke denominator and the step-cap numerator. It is also incoherent: "within the
    # current marker's window" presupposes a marker.
    # Heartbeat: proves to the NEXT session that this one was alive here. Without it,
    # ownership alone cannot distinguish a live peer from a marker abandoned mid-pipeline,
    # and the guard wedges the project for the full TTL (round-4 P0).
    autopilot.touch(root, session_id=args.session_id)
    _confirm_entry(root, stage=args.current, marker=marker)
    # Unknown `--current` (typo / stage outside the pipeline) is checked FIRST — BEFORE the
    # caps — so a bad value can't trigger the marker-clearing cap path and silently kill the
    # session while falsely claiming a cap halt (REVIEW P3). Marker preserved; the user fixes
    # the typo and re-runs (the cap still applies on the corrected call).
    # It is also BEFORE the slug resolution, which WRITES `task_slug_stage` to the marker:
    # resolving first meant `--current bogus --slug s` stamped `bogus` as the supplying
    # stage and then returned "marker preserved", which was no longer true.
    # marker.pipeline holds AtomicStage (str-enum) members; `in` uses str-equality so a plain
    # stage name like "research" matches (str(member) gives the enum repr — do NOT stringify).
    if args.current not in marker.pipeline:
        out["halt_kind"] = "unknown_stage"
        out["reason"] = f"current stage {args.current!r} not in the pipeline — marker preserved"
        print(json.dumps(out))
        return 0
    slug, slug_source = _resolve_task_slug(
        root, marker=marker, flag_slug=args.slug, stage=args.current, session_id=args.session_id
    )
    out["task_slug"] = slug
    out["task_slug_source"] = slug_source
    if slug_source in ("rejected", "rejected-fallback"):
        # Do NOT authorize. The prompt is told not to run on a substitute slug, so
        # emitting `proceed: true` + an `advance_authorized` row here would either strand a
        # pending authorization (model obeys) or advance the wrong task (model does not) —
        # and a later retry's authorization would then be confirmed against THIS one by the
        # greedy pairing. Halting is the only self-consistent answer.
        out["halt_kind"] = "bad_slug"
        out["reason"] = (
            f"--slug {args.slug!r} failed validation — fix the slug and re-run; "
            "no advance was authorized"
        )
        print(json.dumps(out))
        return 0
    # Counts stages ENTERED, not authorizations granted (ADR-004) — the cap must bound
    # work actually performed.
    steps = autopilot_ledger.count_entries(root, since=marker.created_at)
    out["steps"] = steps
    decision = evaluate_boundary(
        root,
        steps=steps,
        step_cap=args.step_cap,
        time_cap_min=args.time_cap_min,
        session_id=args.session_id,
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
        # halted_cap event. (kill_switch leaves no marker to clear.) The old rationale
        # also cited a Stop-hook backstop; that module was deleted in 539f05a9 and its
        # invocations are retired, so the duplicate-row reason is the only one left.
        if decision.halt_kind in ("step_cap", "time_cap"):
            autopilot.clear(root, session_id=args.session_id)
        print(json.dumps(out))
        return 0
    # `blocked` is a caller ASSERTION that a quality threshold failed, so it is honoured on
    # ANY stage, not only the two that own a judgment gate. Today no other stage's template
    # sends it, so this is future-proofing rather than a fail-open being closed — but the
    # asymmetry is the point: the value whose entire purpose is to stop must never be a
    # silent no-op, and a stage gaining a threshold gate should not also have to be added to
    # `_JUDGMENT_GATED_STAGES` before its `blocked` is honoured.
    if args.judgment_gate == "blocked":
        autopilot_ledger.append_event(root, event="gate_blocked", fields={"stage": args.current})
        out["halt_kind"] = "judgment_gate"
        out["reason"] = (
            f"stage {args.current} reported a BLOCKED gate — a quality threshold, not a "
            "judgment. No level clears it, auto_full included. Fix the underlying failure "
            "and re-run. Marker preserved."
        )
        print(json.dumps(out))
        return 0
    # ADR-009 — the judgment gate. Placed AFTER the caps and BEFORE the human gate: the caps
    # are terminal and must win, while the land gate must remain reachable on the next call
    # (this halt preserves the marker, so it will be).
    if args.current in _JUDGMENT_GATED_STAGES and args.judgment_gate != "clear":
        # ABSENT (None) is NOT `pending`, and conflating them was a P0 in the first attempt at
        # this fix. `pending` is a caller SAYING "a judgment is unresolved" — a claim
        # `auto_full` is licensed to answer. Absence is the caller saying nothing at all: a
        # forgotten flag, or a harness rendered before this flag existed. Defaulting absence
        # to `pending` therefore reopened the exact hole at the exact level where it is most
        # dangerous, because `auto_full` cleared it. Absence is un-clearable at EVERY level.
        if args.judgment_gate is None or marker.level != "auto_full":
            # NOT terminal, and NOT a marker clear. `merge_gate` below clears the marker
            # because landing ends the session; copying that here would end the autopilot
            # session at the first plan stage — and starve `smoke_check` of the very rows
            # that let `/hm:health` tell "stopping correctly" from "never fires".
            autopilot_ledger.append_event(
                root, event="gate_blocked", fields={"stage": args.current}
            )
            out["halt_kind"] = "judgment_gate"
            if args.judgment_gate is None:
                out["reason"] = (
                    f"stage {args.current} passed no --judgment-gate verdict, which is "
                    "un-clearable at every level including auto_full. Most likely you "
                    "omitted the append your Step 1 asked for: re-run this command with "
                    "exactly one of --judgment-gate clear|pending|blocked. Only if your "
                    "rendered stage never mentions --judgment-gate at all is this a stale "
                    "render — then, and only then, /harness-maker:make --update. "
                    "Marker preserved."
                )
            else:
                out["reason"] = (
                    f"stage {args.current} has an unresolved judgment gate and the level is "
                    f"{marker.level} — autopilot stopped; resolve it and re-run. "
                    "Marker preserved."
                )
            print(json.dumps(out))
            return 0
        # auto_full: answer rather than stop. The directive is the whole point of the level —
        # the answer must be RECORDED where a human will find it, or this is an unlogged
        # skip of a human decision.
        out["judgment_auto_answered"] = True
        # Written HERE, at the moment the judgment is answered — not later, on the advancing
        # path only. Round 2 filed "the row fires on runs that then stop at the land gate";
        # round 3 filed the inverse, that suppressing it makes such a run byte-identical on
        # the ledger to a `clear`-gate `auto_safe` run. Round 3 wins: the row's question is
        # "was a human judgment cleared?", and the answer is yes regardless of what the chain
        # did next. The outcome is a FIELD, so both questions stay answerable.
        autopilot_ledger.append_event(
            root,
            event="gate_auto_answered",
            fields={
                "stage": args.current,
                "level": marker.level,
                "advanced": next_stage(marker.pipeline, args.current)
                not in (None, *_HUMAN_GATED_STAGES),
            },
        )
        out["judgment_directive"] = (
            f"level auto_full: the {args.current} judgment gate was ANSWERED for you rather than "
            "stopped at — read `proceed`/`halt_kind` for what the chain then did. Record the "
            "answer you took — for `plan`, write the recommended option into the PLAN's "
            "Interview Transcript; for `review`, write the passed-over finding ids into the "
            "REVIEW document. An unrecorded auto-answer is an unauditable skip."
        )
    nxt = next_stage(marker.pipeline, args.current)
    if nxt is None:
        # `current` IS the last stage → end the session (ADR-006).
        autopilot.clear(root, session_id=args.session_id)
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
        autopilot.clear(root, session_id=args.session_id)
        out["halt_kind"] = "merge_gate"
        out["next_stage"] = nxt
        out["reason"] = (
            f"next stage {nxt!r} is human-gated (merge/push, ADR-002) — "
            "autopilot stopped; invoke it manually"
        )
        print(json.dumps(out))
        return 0
    # AUTHORIZED, not entered — the next stage's own boundary/gate-blocked call confirms
    # entry (ADR-004/005). Writing "advanced" here was the bug: it recorded permission as
    # if it were progress.
    autopilot_ledger.append_event(root, event="advance_authorized", fields={"to": nxt})
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
    # ADR-003: the stage terminal supplies the slug it is working on; boundary persists it
    # and hands it to the next stage's `Skill(hm:<stage> <slug>)` call.
    b.add_argument("--slug", default=None)
    # PLAN-sessionid-env-propagation ADR-005. NOT optional in practice: the marker
    # writer stamps an id, and `_is_own` compares whenever EITHER side has one, so an
    # id-less reader resolves an id-bearing marker as foreign -> kill_switch. Empty
    # string means id-less (Cursor/Codex/degraded), which is the pre-existing behaviour.
    b.add_argument("--session-id", default=None, dest="session_id")
    # ADR-009: `default=None` — a SENTINEL, deliberately not `"pending"`. Absence means the
    # caller said nothing (a forgotten flag, or a harness rendered before this flag existed);
    # `pending` means the caller said "a judgment is unresolved", which `auto_full` may
    # answer. Defaulting absence to `pending` made the two indistinguishable and reopened the
    # P0 this flag exists to close, at the one level where it matters. Not `required=True`
    # either: an argparse error on the six non-judgment stages would break every caller.
    b.add_argument(
        "--judgment-gate",
        default=None,
        choices=("pending", "clear", "blocked"),
        dest="judgment_gate",
    )
    b.add_argument("--step-cap", type=int, default=None, dest="step_cap")
    b.add_argument("--time-cap-min", type=int, default=None, dest="time_cap_min")
    # gate-blocked (P7): the auto-branch records this when a mandatory gate holds the chain
    # — distinct from a cap halt, so the ledger shows WHY the chain stopped.
    g = sub.add_parser("gate-blocked", add_help=False)
    g.add_argument("--root", default=".")
    g.add_argument("--stage", required=True)
    g.add_argument("--session-id", default=None, dest="session_id")
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
        marker = autopilot.active_marker(root, session_id=args.session_id)
        if marker is None:
            return 0
        autopilot.touch(root, session_id=args.session_id)
        # A stage that reaches its gate DID start — so this call confirms entry too
        # (ADR-005). Same placement rule as boundary: after the marker check, never before.
        _confirm_entry(root, stage=args.stage, marker=marker)
        autopilot_ledger.append_event(root, event="gate_blocked", fields={"stage": args.stage})
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main(argv) in tests
    sys.exit(main())
