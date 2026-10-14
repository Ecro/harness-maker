---
type: spec
task_slug: hm-light-lane
status: draft
created: 2026-10-14
tags: [harness-maker, spec, jinja2, cost, spec-stage, execute, review, skills]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
summary: "Stage 1 of HM-LIGHT-LANE: light lane, compact spec_machine check, typed-only internal skills"
---

# SPEC — hm-light-lane (stage 1)

## 🎯 Intent

On the 2026-10-14 bench the full /hm: pipeline cost ×22 a plain run on single-session tasks with
no hidden-test gain, and both of its failures were Phase A.5 self-blocks. About 75% of that cost is
context carried in the main loop. Intent HM-LIGHT-LANE takes five levers; this SPEC is stage 1:
the light lane itself, lever 4 (`spec_machine check` output) and lever 5 (skill listing).

## 🌅 Outcomes

- spec Step 0 classifies every non-trivial task as `lane: light` or `lane: full` and writes it to
  the SPEC frontmatter with a logged reason. The trivial skip path is `light`. A SPEC without the
  field is `full`.
- On `light`, execute skips Phase A.5 only; Phase A, A.4 and B still run.
- On `light`, review keeps every lens, the coverage check and the Grade Gate, and drops Pass 1,
  caps rounds at 2, and skips a Confirmation Pass that would re-review an unchanged artifact.
- A clean `hm spec_machine check --all` prints one line.
- Five internal skills and seven user-typed commands carry `disable-model-invocation: true`.
- The shipped command surface does not grow: rationale paragraphs that change nothing at run time
  move to `docs/reference/stage-rationale.md`.

## 📋 In-Scope Scenarios

### S1: A small task takes the light lane
**Given** a non-trivial task that touches about five files, fits one session and has no irreversible decision
**When** `/hm:spec` runs Step 0
**Then** the SPEC frontmatter has `lane: light` and Refinement Decisions carries the reason

### S2: The light lane skips A.5 and nothing else in execute
**Given** a SPEC with `lane: light`
**When** `/hm:execute` reaches Phase A.5
**Then** it goes to Phase B and records a `dispatch-skipped` ledger row
**And** Phase A, A.4 and B are unchanged

### S3: Old SPECs keep the full pipeline
**Given** a SPEC written before this change, with no `lane` field
**When** execute or review reads it
**Then** the lane is `full`

### S4: Light review cuts repetition, not coverage
**Given** a SPEC with `lane: light`
**When** `/hm:review` runs
**Then** it dispatches every lens once with no Pass 1, caps `max_review_rounds` at 2, and skips the Confirmation Pass when round 1 approved with no fix applied

### S5: A clean check prints one line
**Given** a SPEC pair that validates, cross-validates and scores with no weak dimension
**When** `hm spec_machine check --all` runs
**Then** stdout is one line `{"ok": true, "overall": N, "strictness": S}` and the exit code is 0

### S6: Internal skills leave the listing, invocable ones stay
**Given** a fresh render
**When** the skill and command frontmatters are read
**Then** the five internal skills and seven user-typed commands carry `disable-model-invocation: true`
**And** the stage commands, `/hm:health` and the skills a stage reaches by name do not

## 🚫 Non-Goals

- Levers 1–3 (stage delegation, body slimming beyond moved rationale, subagent results to files): stages 2–3 of the intent.
- The bench runner and re-measurement: stage 4.
- Changing any gate on the full lane.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | repo standard |
| Surface | aggregate shipped chars ≤ baseline | `test_aggregate_shipped_surface_does_not_grow` |
| Compatibility | missing `lane` = `full` | every existing SPEC keeps today's behaviour |
| Security | `security-scanner` stays invocable | security-reviewer defers to it when available |

## 🔒 Irreversible Decisions

none

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `tests/render/test_render_light_lane.py::test_spec_step_0_decides_the_lane_and_writes_it` |
| S2 | unit | `tests/render/test_render_light_lane.py::test_execute_skips_only_a5_on_light` |
| S3 | unit | `tests/render/test_render_light_lane.py::test_execute_reads_a_missing_lane_as_full` |
| S4 | unit | `tests/render/test_render_light_lane.py::test_review_light_lane_skips_pass_1_and_the_unchanged_confirmation` |
| S5 | unit | `tests/unit/test_spec_machine_check_all.py::test_a_clean_pass_prints_one_short_line` |
| S6 | unit | `tests/render/test_render_light_lane.py::test_internal_skill_is_typed_only` |

### AC-001: Spec Step 0 decides the lane and writes it
### AC-002: The SPEC frontmatter carries the lane
### AC-003: Execute skips only Phase A.5 on the light lane
### AC-004: A SPEC without a lane reads as full
### AC-005: Review keeps the lens axis and caps repetition on light
### AC-006: Review skips Pass 1 and an unchanged confirmation pass on light
### AC-007: A clean spec_machine check prints one short line
### AC-008: Internal skills and user-typed commands leave the skill listing

## ❓ Open Questions

- Whether the lane cuts reach ×5 is unmeasured until the bench runner exists (stage 4).

## 🔍 Refinement Decisions

- Round 0: requirements came from the confirmed intent draft and the token-lever analysis (user chose to fold all five levers into this intent, 2026-10-14). lane: full — this change spans more than five files.
- A.4 stays on the light lane although the draft listed it: it is one test run and is registered INV (agent decision).
- Review lenses stay: 11% of cost, fixes in 5 of 13 runs (research thread, 2026-10-14).
