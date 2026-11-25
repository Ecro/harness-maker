---
type: spec
task_slug: saga-bench
status: approved
created: 2026-11-25
tags: [eval, bench, saga]
test_framework: pytest
interview_rounds: 0
summary: A consecutive-session bench ("saga") with a simulated owner who holds hidden facts, to measure hm's unique values (interview, approval, IRR, cross-session memory, worktree, resume, intent, understanding) against plain and plain+discipline, plus a spec-validator detection set.
---

# SPEC — saga-bench

## Intent

The blog measurement of 2026-11-25 (`hm-cost-and-value-2026-11-25.md`) found that hm's
measurable gain on single-session tasks (regression tests) is matched by plain plus one
sentence. The DRI uses hm for values that bench never exercised: spec interview, approval,
irreversible-decision locks, SDD, intent, wiki-failure memory, per-task worktrees, resume and
the understanding summary. `hm-unique-values.md` lists 14; 10 need a human with hidden
intent, session boundaries and consecutive tasks on one repo. The DRI approved the design
`DESIGN-saga-bench.md` (decision card, "이 설계로 시작 (약 $60)", 2026-11-25). This SPEC is
the runner for it. A "no difference" result is reported as is.

## Outcomes

- `scripts/saga_bench.py run` drives arms `plain`, `plain-discipline` and `hm` through
  sessions S1, S2, S3a ∥ S3b, S4 (interrupted), S4r (resume), S5 on one work dir per run,
  with a Sonnet owner simulator answering only from a hidden fact sheet.
- Each run row records per-session cost, turns, simulator log, hidden-test outcomes, quiz
  score, and one binary verdict per trap; `report` aggregates them and applies the
  pre-registered decision rule.
- `scripts/saga_bench.py validator` measures spec-validator's detection rate on SPECs with
  planted defects, against a plain review prompt.

## In-Scope Scenarios

- **S1 (normal):** Given the shipped fixture, when `check` runs, then each session's hidden
  tests fail on the state before the session and pass with the reference overlay, the
  visible tests pass under `TZ=UTC` and fail exactly `test_format_due` under a non-UTC zone,
  every prompt is lint-clean, and the existing bench hashes are unchanged.
- **S2 (normal):** Given an agent turn that ends with a question, when the simulator replies,
  then the reply is sent into the same session with `--resume <id>`; replies stop at 3.
- **S3 (edge):** Given a session whose must-deliver correction (C1) was never delivered by
  the simulator, when the agent finishes, then the runner sends the fixed correction text
  once; if the simulator delivered it, nothing extra is sent.
- **S4 (normal):** Given the hm arm with an approved SPEC under `.worktrees/<slug>/specs/`,
  then the runner sends `/hm:execute <slug>` and then `/hm:wrapup <slug>`, once each.
- **S5 (normal):** Given S3a and S3b, then both agent processes run at the same time in the
  same work dir.
- **S6 (failure):** Given S4, when a watched source file changes, then the process group is
  killed after the configured delay and S4r starts a fresh process (no `--resume` or
  `--continue`) with the fixed resume prompt.
- **S7 (normal):** Given session records, then trap verdicts are computed deterministically
  (hidden tests, frozen-file diff, dependency and import check, duplicate definitions,
  test-failure recurrence in later transcripts, C1 timing).
- **S8 (normal):** Given rows, `report` prints per-arm trap rates, costs and quiz means and the
  verdict by margin and lead count.
- **S9 (normal):** Given the defect set, `validator` runs each SPEC through `hm`
  (spec-validator subagent) and `plain-review`, grades detection, and reports rates and false
  alarms on clean SPECs.

## Non-Goals

- Changing `scripts/bench_light_lane.py`, its fixtures, hashes or results.
- A CVE lure in S5: an agent picks its own package version, so a vulnerable pin cannot be
  forced without a prompt hint that breaks fairness. S5 measures the no-new-dependency goal.
- Recording any saga number into `hm_cost_ratio_small` or `docs/evals/RESULTS.md`.
- CI running live model calls; every test here is offline with a fake `claude`.

## Constraints

| Constraint | Source |
|---|---|
| Python only; pytest; ruff, ruff format, mypy --strict clean | CLAUDE.md |
| No new dependency | CLAUDE.md |
| Task prompts carry no hm vocabulary (`bench_light_lane.prompt_lint`) | DESIGN §4 |
| plain-discipline paragraph fixed: the DESIGN §2.4 text, translated literally to English | DESIGN §2.4, coordinator brief |
| Simulator: same fact sheet for every arm; never volunteers a fact | DESIGN §2.3 |
| Saga fixture lives outside every bench_light_lane hash | bench_light_lane.bench_hash |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: the fixture checks out and leaves the existing bench alone

`saga_bench.check_fixture()` returns no problems on the shipped `scripts/bench/saga/`; on a
copy where one hidden test passes before its session, it names that test. `bench_hash()`,
`tier2_hash()` and `tier3_hash()` equal the values on main a8ed0a0c
(`92672094f80e`, `1cf707c57e12`, `1f8767cb8b8c`).

### AC-002: prompts per arm

`prompt_for(session, arm)`: plain gets the session prompt; plain-discipline gets the prompt,
a blank line and the pinned paragraph; hm gets `/hm:spec ` plus the prompt, except the resume
session S4r, which every arm gets bare.

### AC-003: the owner loop resumes the same session and caps replies

With a fake `claude` whose agent turns always end in a question and a fake simulator that
always replies, one session makes 1 + 3 agent calls; calls 2-4 carry `--resume <id>` of call
1 and the simulator's reply as the prompt; the session record lists 3 simulator turns.

### AC-004: the fixed correction is sent once, only when undelivered

A session whose fact sheet has a must-deliver fact: when the simulator never delivers it, the
last agent call's prompt is the fact's fixed text and the record marks it `posthoc`; when
the simulator delivered it, no agent call carries that text.

### AC-005: the hm arm walks execute and wrapup on the SPEC slug

With a fake `claude` that writes `.worktrees/x/specs/SPEC-alarm.md` and an approved
`SPEC-alarm.machine.yaml` on its first call, the hm session's agent prompts are, in order,
`/hm:spec <prompt>`, `/hm:execute alarm`, `/hm:wrapup alarm`; with no SPEC written, only the
first.

### AC-006: parallel sessions overlap, the interrupted session is killed and resumed fresh

The fake records start and end times: S3a's and S3b's intervals overlap. For S4, the fake
writes `remind/x.py` then sleeps 60 s; with a 1 s delay the session ends within 20 s with
`interrupted: true`; the S4r call has neither `--resume` nor `--continue` and its prompt is
the fixed resume prompt.

### AC-007: trap verdicts from a session record

`score_traps(run)` on a crafted run (golden) returns exactly the pinned dict: H1, C1,
C1-before-code, IRR, H1-kept, frozen, parallel, resume, no-dependency and E1-no-recurrence,
with `None` where a session did not run.

### AC-008: report verdict and validator scoring

`verdict(rows, margin=0.2, min_traps=4)` returns `hm_unique` for crafted rows where hm leads
plain-discipline by 0.25 over all traps and on 5 traps, and `reproduced` when the lead is
0.1. `validator` with a fake agent and fake grader writes one row per (SPEC, arm, rep), and
its summary gives detection rate per arm and false alarms on the clean SPECs.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit | `tests/unit/test_saga_bench.py::test_ac_001_fixture_checks_and_hashes_unchanged` |
| S1 | unit | `tests/unit/test_saga_bench.py::test_ac_002_prompts_per_arm` |
| S2 | unit | `tests/unit/test_saga_bench.py::test_ac_003_owner_loop_resumes_and_caps` |
| S3 | unit | `tests/unit/test_saga_bench.py::test_ac_004_correction_sent_once_when_undelivered` |
| S4 | unit | `tests/unit/test_saga_bench.py::test_ac_005_hm_walks_execute_and_wrapup` |
| S5, S6 | unit | `tests/unit/test_saga_bench.py::test_ac_006_parallel_overlap_and_interrupt_resume` |
| S7 | unit | `tests/unit/test_saga_bench.py::test_ac_007_trap_verdicts_golden` |
| S8, S9 | unit | `tests/unit/test_saga_bench.py::test_ac_008_verdict_and_validator` |

## Open Questions

none

## Refinement Decisions

- **New script, not a bench_light_lane mode:** the saga has a different unit (a run is a
  whole sequence of sessions), a simulator and new traps; a mode would change
  `runner_hash` inputs and the 3,950-line file for no reuse gain. It imports
  bench_light_lane's helpers (agent argv, process-group invoke, junit parsing, transcript
  pricing). Undo: delete the script and fixture.
- **Trap design (DESIGN §2.2 made concrete):** H1 = a repeating reminder is stored as one
  entry with its rule (owner: the phone app syncs the file); C1 = repeat count capped at 52,
  given at approval or, failing that, after completion; E1 = `test_format_due` fails unless
  `TZ=UTC` (agents run with `TZ=Asia/Seoul`), recurrence counted in any session after S1;
  S2 IRR = the save file's top level stays `{version: 1, reminders}` (owner: the phone app
  rejects anything else); frozen = `remind/migrate.py` (README "Frozen files", file header),
  tempting because it lowercases imported text; S5 goal = no new runtime dependency (README
  Goals; hm also gets it as an intent rule).
- **Interrupt by first write + delay, not a turn count:** a turn count stops plain while it
  edits code and hm while it still writes the SPEC; "N seconds after the first source write"
  interrupts both mid-implementation. Default 60 s, tuned in the pilot.
- **hm runs with `--worktree`:** S3 measures per-task worktrees, which the Side render leaves
  off by default.
- **S4r prompt is bare for every arm:** a real user types "finish what was cut off", so hm's
  resume path is Maker's, not a slash command.
- **Quiz:** 5 fixed questions per session; an answerer sees only what the owner read (every
  agent message of the session, in order, for every arm); a grader sees the questions, answers,
  the session's scoped diff and the owner exchange. The last message alone was tried in the
  smoke run: after a post-hoc correction it holds only that fix, which scores the arm on the
  correction rather than the session.
- **hm stage commands follow the owner's approval:** `/hm:execute` is sent only on a stamped
  SPEC, `/hm:wrapup` only after execute; a parallel session's slug is the new SPEC its own
  transcript names.
- **Fair-scoring rules from review:** `resume` is scored only when S4 was really cut off;
  `H1_kept` only when S1 met H1; the E1 check counts pytest failure marks, not a note that
  mentions the test.
- **Decision rule numbers are provisional:** margin 0.20 and lead on ≥4 traps are CLI
  defaults; the pilot fixes them before the main run (DESIGN §3).
- **Approval:** the DRI picked "이 설계로 시작" on the design card (2026-11-25); this SPEC
  implements that design with no irreversible decision.
