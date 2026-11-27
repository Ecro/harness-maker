---
type: spec
task_slug: spec-owner-boundary
status: approved
created: 2026-11-27
tags: [spec-stage, interview, skip-check, hm-check, signals]
test_framework: pytest
interview_rounds: 0
summary: /hm:spec asks the one scope boundary only the owner knows before the SPEC, skips the interview less, and hm check gives gate commands their SIGINT back.
---

# SPEC — spec-owner-boundary

## Intent

The 2026-11-26 replay bench (`/mnt/project-files/hm-blog-cost/replay-results-2026-11-26.md`,
sections 3.2–3.4) replayed real harness-maker PRs from their base commits. hm got **3 of 10**
owner-only facts before code; a plain prompt with a fixed "discipline" paragraph got 8. The
cause was the spec stage:

- In 4 of 10 hm spec sessions, Step 0 judged the change small, skipped the interview and
  stamped `--exempt` itself. R3 edits `check.py` and the README and changes a user-facing
  message. R4a and R4b edit several templates and a CLI output format. None met "one file or
  config; no API, IPC, schema or file-format change", but a detailed ask read as a small one.
- In 4 more, hm wrote the whole SPEC and asked only for approval. The owner-only facts (R3:
  which projects count as having a Python test setup; that a Python project with no runner keeps
  today's reason) sat inside hm's own Refinement Decisions. A simulated owner caught a wrong
  assumption there about half the time, and never when hm did not write the assumption down.
  The same simulator answered an explicit question 4 of 4 times.

Separately, the R2 rerun's wrapup was blocked by one test that fails only when `hm check` runs as
a background job (it also fails at the start commit).

The DRI chose "경계 질문 추가 + Step 0 좁히기" on the decision card (2026-11-27 09:44Z).

## Outcomes

- Before writing the SPEC, `/hm:spec` names the ask's scope boundary: which inputs take the new
  behaviour, which keep the old, and which existing behaviour must stay. When neither the ask nor
  the code settles it, hm asks the DRI that one question in round 1. This is LLM judgement, not
  a rule match. It stays inside the 2026-11-10 "ask only big things" rule (SPEC-ask-less rule R:
  scope is the DRI's).
- The Step 0 skip needs five conditions, not four. Docs count as files and tests do not. A
  CLI-output or user-facing message change disqualifies the skip. An open Boundary disqualifies
  it. The rule says that a detailed ask is not a small one.
- `hm check` gate commands start with SIGINT at its default even when `hm check` itself started
  with it ignored.

## In-Scope Scenarios

- **S1 (normal):** Given any rendered spec stage (Claude command, Codex skill; Side, Production;
  comprehension depth minimal, standard, deep), Step 0 holds the five-condition skip rule, and
  the old four-condition rule is gone.
- **S2 (normal):** Given the same renders, Step 2 holds the Boundary rule before "Ask only what the
  DRI owns", at every depth (the rule is not inside a depth block).
- **S3 (failure → fixed):** Given `hm check` started with SIGINT ignored (`hm check … &` from a
  non-interactive shell), a gate command's Python child has `signal.default_int_handler`.
  `hm check`'s own handler is left unchanged.
- **S4 (live, manual):** Given the replay bench R3 and R4 tasks, the hm arm (2 runs) gets more
  owner-only facts before code than 3/10. Measured with `replay.py` after the change.

## Non-Goals

- A rule-based detector for "owner knowledge" (keywords, file counts in code). The model judges.
- More questions in general: one boundary question, only when the ask and code leave it open.
- Changing the approval flow, spec-validator, or the "decided for you" Refinement Decisions.
- Restoring SIGINT for bare `pytest &` outside `hm check`; this repo's tests keep assuming a
  foreground-like signal disposition.

## Constraints

| Constraint | Source |
|---|---|
| Ask only goal, scope, design, main features, IRR, approval | SPEC-ask-less rule R; DRI 2026-11-10 |
| Spec stage budget raised only by measured growth (+475 → 7620) | `test_overhaul_p1_surface._STAGE_BUDGET` |
| SPEC-ask-less AC-007 growth allowance gains this SPEC's +475 (`_GRANTED = 480`) | `tests/render/test_ask_less.py` |
| No `shell=True`, timeouts kept | implementation-patterns.md |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: the skip check has five conditions

On every arm in S1, Step 0 contains exactly once, before `--exempt`:

> Skip the interview only when all five hold: one file or config (docs count, tests do not);
> acceptance obvious from the title; no API, IPC, schema, file-format, CLI-output or user-facing
> message change (a typo fix is not one); reversible within an hour with no user impact; no open
> **Boundary** (read the code as Step 2 says). A detailed ask is not a small one; when unsure,
> interview.

and the render has no `all four hold`.

### AC-002: the Boundary rule comes before the interview questions

On every arm in S1, the render contains exactly once, inside Step 2, before the Design brief
(when the depth renders one) and before `Ask only what the DRI owns`:

> **Boundary.** Before the SPEC, read the code the ask touches: which inputs take the new
> behaviour, which keep the old, and which existing behaviour must stay? If neither the ask nor
> the code settles that, ask the DRI in round 1 (one of its 3 questions), recommendation first.

### AC-003: gate commands get SIGINT back

A Python driver that sets SIGINT to `SIG_IGN` (or `SIG_DFL`) and calls `check._run` on a child
that prints `signal.getsignal(SIGINT) is signal.default_int_handler` gets exit 0 and `True`
both times, and its own SIGINT handler is unchanged afterwards.

## Verification

| Scenario | Mode | AC / test |
|---|---|---|
| S1 | render | AC-001 `tests/render/test_spec_owner_boundary.py::test_ac_001_skip_check_has_five_conditions` |
| S2 | render | AC-002 `tests/render/test_spec_owner_boundary.py::test_ac_002_boundary_before_the_interview` |
| S3 | unit | AC-003 `tests/unit/test_check_sigint_inherit.py::test_ac_003_gate_child_has_default_sigint` |
| S3 | manual | the two real tests (`test_stop_signal_kills_live_agents_and_skips_queued_cells[sigint]`, `test_external_caller_cancellation_cleans_owned_processes`) run through `check._run` from a background job: pass |
| S4 | live, manual | replay bench R3 + R4 hm arm × 2 (`replay.py`, tasks.json), facts before code vs 3/10 |

## Open Questions

none

## Refinement Decisions

- **The boundary is a named question in Step 2, not a new step:** round 1 already exists and
  already offers approval when nothing is open. The failure was that hm judged nothing open on a
  detailed ask. Naming the boundary (inputs new/old, behaviour that must stay) gives the
  judgement something specific to look for. Cost to undo: one paragraph.
- **One question, recommendation first, counted inside the 3 per round:** it keeps the
  "ask only big things" rule; scope is already the DRI's under rule R.
- **Step 0 points at the Boundary instead of restating it:** one definition, so the skip and the
  interview can't drift apart.
- **SIGINT is restored in `check._run`, not in this repo's conftest:** hm itself tells the model
  to run `hm check` in the background, so hm created the disposition; fixing it at the gate
  helps every project's tests, not just this repo's. `preexec_fn` is safe because `hm check`
  starts no threads. Since the gate runs in its own session, no terminal can deliver SIGINT, so
  the change does not make a background `hm check` interruptible from a terminal.
- **SIGQUIT is left alone:** a background job also starts with it ignored, but no gate or test
  here depends on it. A `preexec_fn` failure is caught with `OSError` as exit 127.
- **"A typo fix is not one":** without it, any edit to an error string or a rendered template
  would block the skip (review F1).
- **Budgets raised by the measured +475, not by a round number:** the wording was trimmed first
  (a first draft was +550; review fixes added 57).
- **Approval:** the DRI's card choice above covers this direction; no irreversible decision, so
  the SPEC is stamped as in SPEC-maker-resume-route. The PR is a design change and the DRI merges.
