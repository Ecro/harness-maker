---
type: spec
task_slug: autopilot-stop-gate
status: draft
created: 2026-10-15
tags: [harness-maker, spec, python, autopilot, hooks, stop-hook]
test_framework: pytest
interview_rounds: 1
lane: full
intent: HM-LIGHT-LANE
summary: "The Stop hook refuses once to end the turn in which autopilot authorized a stage the model never invoked"
---

# SPEC: autopilot does not stop between an authorization and the stage it authorized

## 🎯 Intent
In the 2026-10-15 eval re-run (harness d25e6bb), 6 of 36 hm runs stopped after `/hm:spec`
with a SPEC on disk and no code. In five of them the ledger
(`.claude/observability/auto-advance.jsonl`) ends with `advance_authorized(to=execute)`, and
the transcript shows no `Skill(hm:execute)` call after it. The boundary said proceed; the model
ended the turn instead. No other run ends in this state. t4-hm-1 also ends with an unconfirmed
authorization (`verify`), but its transcript shows `Skill(hm:verify)` and a verify STOP at
Check 4. That is a running stage that halted, which is exactly what the gate must not refuse.

This is the follow-up that `PLAN-autopilot-advance-noop` ADR-001 deferred "on data". The 5/36 is
that data. The earlier Stop-hook backstop was deleted in `539f05a9`. It blocked on the marker
alone, so it refused every later turn's stop, a defect recorded as P2-6 in
`REVIEW-human-bottleneck-auto-advance-fullreview`. This gate is narrower in two ways. It refuses
only in the turn that issued the authorization, and only if the authorized stage was never
invoked.

## 🌅 Outcomes
- In Claude Code, a turn that authorized a stage cannot end silently before invoking it. It is
  refused once, with the stage named, and may then stop.
- In every other state, and on every other host, the Stop hook behaves exactly as it does today.
- The next eval run should show the five post-spec stalls of this shape gone. The eval measures that; this
  SPEC does not gate on it.

## 📋 In-Scope Scenarios

### S1: authorized and never invoked (AC-001, AC-003)
**Given** all of the following:
- this session's autopilot marker is active and not `gated`;
- no other session holds a fresh, id-bearing autopilot marker;
- since the marker's `created_at`, the ledger holds an `advance_authorized(to=<stage>)` with
  `<stage>` in `marker.pipeline`, and no `advance_entered` confirms it;
- the transcript at the payload's `transcript_path` shows, after that row's `ts`, no
  `Skill(hm:<stage>)` call and no user-type entry other than tool results and `isMeta` expansions.

**When** the Stop hook runs with `stop_hook_active` false.

**Then** it prints `{"decision": "block", "reason": …}` naming `/hm:<stage>` and exits 2.

### S2: a running stage is never refused (AC-001, AC-003)
**Given** S1's state, except the transcript shows `Skill(hm:<stage>)` after the authorization.
The stage is running: it may be asking a question, halted on a failing test, or dead partway
through.
**When** the Stop hook runs.
**Then** it exits 0 with no output.

### S3: a later turn is never refused (AC-001)
**Given** S1's state, except a user or task-notification entry follows the authorization
**When** the Stop hook runs
**Then** it exits 0. The person has had the floor, so a pause they asked for holds.

### S4: second stop, other states, other hosts (AC-001, AC-002)
**Given** any of the following:
- `stop_hook_active` true;
- no marker, or a gated, foreign or expired marker;
- a peer session armed;
- a confirmed authorization, or one older than the marker, or one outside `marker.pipeline`;
- a missing or unreadable ledger or transcript (the Codex case);
- a session whose own loop marker is active.

**When** the Stop hook runs.

**Then** it does what the df070f6c loop gate does: block only for this session's loop marker,
with that reason unchanged.

## ✔️ Acceptance Criteria

### AC-001
The stop-hook decision is the golden function of marker, ledger, transcript and payload state (S1–S4).

### AC-002
Without a refusing state the stop hook equals the df070f6c loop gate.
Stdout and exit code are the same on every loop-marker case (S4).

### AC-003
Replaying the eval-2 hm runs blocks exactly the five stalled runs, and no other run at its end or at any stage start.
The replay uses each run's ledger and transcript. Every completed run is also cut right after each
`Skill(hm:<stage>)` call, and no cut is blocked (S1, S2).

### AC-004
The block reason names the stage and how to proceed or stop.
Concretely, it contains `/hm:<stage>`, the `Skill` tool, and the sentence that ending the turn
again stops (S1).

## 🚫 Non-Goals
- The full-lane approval hold (t12-hm-2). Holding there is correct; the bench has nobody to
  approve.
- Questions asked in a non-interactive run (t10-hm-3), as a behaviour. The gate refuses that stop
  only because t10-hm-3 also left `execute` authorized and never invoked it.
- Codex. Its Stop payload's transcript format is not known here, so the gate fails open there.
- Cursor. Its `stop` hook runs only telemetry, and the Claude copy of `loop_gate` exits early.
- A new rendered hook entry or module, or any change to `settings.json`, `.cursor/hooks.json` or
  `.codex/hooks.json`. The check lives in `loop_gate --mode stop-hook`, which Claude Code already
  runs on Stop.
- Session-scoping the ledger. That is a file-format change. A peer's armed marker makes the gate
  fail open instead (S4).

## ⚙️ Constraints
- **Framework and fixtures.** Use `pytest`, with tests in `tests/unit/test_autopilot_stop_gate.py`.
  Fixtures go in `tests/fixtures/autopilot_stop_gate/`. They are byte copies of the eval-2 ledgers,
  plus transcripts reduced to the fields the gate reads (`type`, `timestamp`, `isMeta`,
  `isSidechain`, `origin`, and the content block types, `Skill` input and tool-result marker), with
  all text dropped.
- **Pairing.** Use `autopilot_ledger.find_unconfirmed_authorization(to=<stage>,
  since=marker.created_at)` for each stage in `marker.pipeline`. The marker comes from
  `autopilot.active_marker`, and a peer marker from `autopilot.other_keyed_markers`. Do not write a
  second pairing implementation.
- **Timestamps.** Compare a ledger `ts` and a transcript `timestamp` as parsed UTC instants. This
  is the only place the two files are ordered against each other.
- **Precedence.** When this session's loop marker blocks, print its reason unchanged and skip the
  autopilot check.
- **Fail open.** Any error reading the marker, ledger or transcript exits 0 and writes one
  `[loop-gate] warn:` line to stderr. So does a transcript with no Claude Code record (no
  `type: user|assistant` line carrying a `message`), which is what keeps a foreign format from
  reading as "never invoked". The hook keeps its 10 s timeout.
- **Replay cuts.** An AC-003 cut drops both every transcript line and every ledger row stamped
  after the cut instant.
- **Early exit.** `is_claude_copy_in_cursor` stays the first check in `main()`.

## ✅ Verification
| Scenario | Mode | Oracle |
|---|---|---|
| S1–S4 | unit | golden table of states (AC-001) |
| S4 | unit, differential | df070f6c `loop_gate` via `git show` (AC-002) |
| S1, S2 | unit, replay | golden: the five runs and the Skill-call cuts read from the eval-2 runs (AC-003) |
| S1 | unit | golden substrings (AC-004) |

## ❓ Open Questions
None.

## Refinement Decisions
- **Lane `full`.** The change touches few files and makes no irreversible decision. It still
  revives a mechanism that was deleted on purpose, and its false positives show up only in
  interactive use. The full lane keeps review and verify.
- **The transcript decides "started".** `advance_entered` is written only at the next stage's own
  boundary, so an unconfirmed authorization covers the whole of that stage's body. Only a
  `Skill(hm:<stage>)` call proves the stage started.
- **A later user entry ends the gate's interest.** This removes P2-6's every-turn refusal. It also
  makes "the user asked to pause" safe without `hm autopilot off`.
- **Extend `loop_gate` rather than add a hook.** There is no render change, and its
  `stop_hook_active` guard already limits refusals to one per stop.
- **`irreversible_decisions: []`.** The block reason is prompt text. No file format, CLI flag or
  ledger field changes.
- **spec-validator** returned MAJOR_REVISION. This revision covers its findings:
  - P0: started versus authorized;
  - P1: peer sessions, the pause path, and the lane;
  - P2: narrowing, gated markers, collapse, host claims, and oracle provenance.
