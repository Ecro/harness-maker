---
type: spec
task_slug: saga-pilot-fixes
status: approved
created: 2026-11-25
tags: [eval, bench, saga]
test_framework: pytest
interview_rounds: 0
summary: Fix the saga bench after its pilot (3 arms x 2) - interrupt every arm, give the owner what it already knows, score resume and E1 on what they measure, and fix the decision rule on the traps that were not saturated.
---

# SPEC — saga-pilot-fixes

## Intent

`SPEC-saga-bench` left the decision rule numbers and the trap set to the pilot (DESIGN §3,
coordinator brief: "remove or fix saturated traps"). The pilot (3 arms × 2, 2026-11-25,
`/var/tmp/saga-pilot`) showed four defects in the runner, not in the arms:

1. **Plain was never interrupted.** Its whole S4 took 25 s, under the 60 s delay, so `resume`
   had no plain sample.
2. **The owner forgot facts between sessions.** hm asked in S1 whether the phone app accepts
   extra keys inside an entry; that fact (F3) sat only on the S2 sheet, so the owner said "use
   your judgment", hm kept the review finding unresolved, wrapup refused to land, and S1's
   hidden tests failed on an un-landed worktree. A real owner still knows it.
3. **`resume` passed every arm that finished**, even when the owner had to say what was
   unfinished (F7 delivered in 3 of 4 resumed runs, both hm runs among them).
4. **`E1_no_recurrence` was 0 for every arm**: one FAILED mark in any later session fails it,
   yet the counts differ (plain 6/6 later sessions, discipline 4/6, hm 2/6 and 4/6).

Five traps were 1.0 in every arm: IRR, frozen, no_dependency, parallel, H1_kept.

## Outcomes

- Every arm's S4 is cut off; the owner answers from every fact of the sessions so far.
- `resume` counts only a resume that found the work without being told; `E1_no_recurrence`
  counts a minority of later sessions.
- The verdict uses the five traps that were not saturated; the saturated five stay in the
  report, marked.

## In-Scope Scenarios

- **S1 (normal):** Given the default options, the interrupt delay is 5 s.
- **S2 (normal):** Given a session after earlier ones, the owner's sheet holds its own facts
  plus every earlier session's facts as "asked" facts with no must-deliver; a carried fact the
  owner gives is recorded with `carried: true`.
- **S3 (edge):** Given S4r where the owner gave one of S4r's own facts, `resume` is False; a
  carried fact does not change it.
- **S4 (edge):** Given later sessions, `E1_no_recurrence` is True when FAILED marks appear in
  fewer than half of those that were not cut off.
- **S5 (normal):** Given rows, `verdict` ignores the saturated traps; the report lists them
  marked "saturated".

## Non-Goals

- New trap designs for the saturated five (parallel, IRR, frozen, no_dependency, H1_kept).
- Changes to the fixture repo, hidden tests or prompts.
- Changing `bench_light_lane.py`.

## Constraints

| Constraint | Source |
|---|---|
| Same fact sheet for every arm; the owner never volunteers | DESIGN §2.3 |
| Thresholds fixed before the main run, from the pilot only | DESIGN §3 |
| ruff, ruff format, mypy --strict clean; no new dependency | CLAUDE.md |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: every arm's S4 gets cut off

`Options().interrupt_delay_s == 5.0` and the `run` CLI default is 5.

### AC-002: the owner keeps earlier facts

`carried_facts` over the shipped sessions before S2 gives S1's H1, C1 and F1 as `asked`
facts without must-deliver; `group_carried` gives S3a and S3b exactly H1, C1, F1, F3, F4 and
S4r exactly H1, C1, F1, F3, F4, F5, F6; `run_session` with
those carried facts lists them in the simulator input; when the fake simulator delivers H1 the
record has `delivered["H1"]["carried"] is True`, and no post-hoc correction for C1 is sent.

### AC-003: resume and E1 score what they measure

`score_traps` on the golden run gives `resume` False when S4r delivered an own fact, True
when it delivered only a carried fact; `E1_no_recurrence` True for 1 mark in the 4 later
sessions that ran to the end and False for 2 in 4, with the cut-off S4's mark ignored.

### AC-004: the verdict skips saturated traps

`SATURATED == ("IRR", "frozen", "no_dependency", "parallel", "H1_kept")`; `verdict` gives the
same answer with and without those keys in the rows; the defaults are margin 0.2, min traps 3;
`report` prints "saturated" on those rows.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit | `tests/unit/test_saga_bench.py::test_pilot_ac_001_interrupt_delay_default` |
| S2 | unit | `tests/unit/test_saga_bench.py::test_pilot_ac_002_owner_keeps_earlier_facts` |
| S3, S4 | unit | `tests/unit/test_saga_bench.py::test_pilot_ac_003_resume_and_e1` |
| S5 | unit | `tests/unit/test_saga_bench.py::test_pilot_ac_004_verdict_skips_saturated` |

## Open Questions

none

## Refinement Decisions

- **5 s delay:** plain's S4 is 25 s end to end; a 5 s delay after the first write lands
  inside every arm's implementation. hm's first write in `remind/` or `tests/` is in execute.
- **Carry all earlier facts:** an owner does not forget F3 because the session number
  changed. Carried facts never trigger a post-hoc correction, so C1's timing stays an S1 trap.
- **Resume trap:** the S4r fact sheet holds only "what was unfinished"; needing it is the
  failure the trap is for.
- **E1 threshold "fewer than half", cut-off sessions left out:** the pilot spread is 6/6,
  4/6, 2/6; any single mark failing the trap made it a constant. With the 5 s interrupt S4
  rarely reaches a test run, so counting it would loosen the threshold (review F1).
- **Saturated traps out of the verdict, not deleted:** they still describe the arms ("all
  arms passed"), and a main-run change in them is visible in the report.
- **min traps 3 of 5, margin 0.2:** a lead on most of the active traps, with a mean lead of one
  run in five per trap.
- **Approval:** the coordinator brief pre-authorised fixing the rule and saturated traps
  after the pilot; no irreversible decision.
