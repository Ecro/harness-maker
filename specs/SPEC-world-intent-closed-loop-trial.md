---
type: spec
task_slug: world-intent-closed-loop-trial
status: approved
created: 2026-09-22
tags: [harness-maker, spec, intent, field-validation]
test_framework: pytest
tier: 2
interview_rounds: 1
intent: WORLD-INTENT-CLOSED-LOOP
summary: "User assessment of the next three real task feedback cycles after workflow activation"
---

# Real-task feedback continuity trial

## 🎯 Intent

Demonstrate the outcome in `intent/WORLD-INTENT-CLOSED-LOOP.md` after
[implementation](SPEC-world-intent-closed-loop.md) is applied. This separates
implementation completion from adoption evidence without waiving either.

## 🌅 Outcomes

The user can assess all three consecutive real tasks from execution and
conversation evidence. The baseline remains unmeasured. A successful trial
requires all three tasks to connect observations to state updates and next
decisions without a user reminder to reconnect feedback.

## 📋 In-Scope Scenarios

### S1: Ordered enrollment and complete assessment
**Given** the implemented workflow is applied here and its revision and activation
timestamp are recorded before enrollment.
**When** the next three distinct real task slugs start in this repository.
**Then** enroll all three in start order, keeping failures, aborts and missing
evidence. Resume/reruns of one slug are one task. Synthetic fixtures and the
already-started implementation task do not count. This trial's administrative
setup is not a qualifying real task; it must not create work to fill the sample.
**And** observe until all three enrolled tasks have terminal dispositions,
regardless of concurrent completion order. Link every row to execution and
conversation evidence and obtain the user's final assessment.

### S2: Honest partial or failed outcome
**Given** fewer than three tasks, missing evidence, unfinished assessment or a
confirmed continuity failure.
**When** trial status is reported.
**Then** collection (`not_started`, `collecting`, `complete`) and outcome are
separate. Outcome is `failed` if any task has a confirmed continuity failure;
otherwise `insufficient_evidence` if a terminal row lacks required evidence;
otherwise `pending` until all three are assessed; otherwise `passed` only if all
three succeed. New evidence can resolve insufficiency, never erase a confirmed
failure. Report failures even while collection continues. No automatic reset or
row replacement is allowed. Starting another trial requires a new user decision.

## 🚫 Non-Goals

No product changes, extra tasks manufactured for enrollment, path migrations,
automatic user assessments, automatic intent closure or approval bypass.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest for collection helpers if needed; manual final assessment | Fixtures cannot prove real behavior |
| Compatibility | Existing intent, SPEC, PLAN and state locations | Operator chose no migration |
| Security | Existing authority and consent | Normal approval questions do not count as failure |
| Window | Activation through all three enrolled tasks reaching terminal disposition | Concurrent completion order must not truncate evidence |
| Performance | Observe real work; no polling or artificial tasks | Trial must not create its own apparent adoption |
| Evidence | Trial PLAN `Trial` section links slugs, starts, terminals, observations, state updates, decisions and user assessment | One authoritative trial record |

The workflow agent collects evidence and proposes an assessment. The user makes
the final assessment; an independent reviewer may verify its evidence and recorded
assessment but cannot substitute its own approval. A user feedback-reminder is a
continuity failure. Normal decision/approval questions and justified termination
can pass, even if the underlying task was aborted. No relevant observation or
insufficient trace evidence cannot establish a successful cycle.

## 🔒 Irreversible Decisions

None beyond IRR-001 in the implementation SPEC: the trial record is
`work-docs/PLAN-world-intent-closed-loop-trial.md`, section `Trial`.

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | manual, evidence rubric | User reviews three rows against world_intent_real_task_trial; independent reviewer checks recorded judgments and evidence |
| S2 | manual, evidence rubric | Inspect enrollment completeness, evidence gaps, failure precedence and retained rows |

### AC-001: Three real tasks receive evidence-based user assessment

Apply `world_intent_real_task_trial` to the trial PLAN and its linked source
records. Pass requires three successful user assessments, each grounded in the
observation → authorized state update → next decision → authorized execution or
justified termination trace. Rubric provenance is the existing intent and the
operator's 2026-09-22 choice of this repository's next three real task slugs.
It is independent of the implementation and cannot be fulfilled by test fixtures.

## ❓ Open Questions

The user accepted this SPEC; future source evidence remains pending. This SPEC is
not implementation's landing gate; its completion remains a condition of intent
attainment. It must not be marked fully verified before the real trial passes.

## 🔍 Refinement Decisions

2026-09-22: operator selected this repository's next three tasks and separate
implementation versus field-validation reporting. A second SPEC under the same
intent prevents the field trial from blocking application of the implementation.

## 🔎 Spec Validation

- Structural/schema and Markdown/YAML cross-validation: passed at block strictness.
- Second opinion: `model: codex`, `status: invoked`, `reason: null`.
  The initial findings were resolved: all-three-terminal window for concurrent
  tasks (`a758ad1b050dd7df`), failure versus pending state precedence
  (`818f4324c58b94ce`), and unprompted connection at each required trigger
  (`1a825b6831a1eb09`).
- One-pass spec-validator assessment: `APPROVED`. No circular-oracle,
  irreversible-decision or scope-boundary finding. Its one suggestion, to name
  the separate trial PLAN explicitly in the authoritative-location table, was
  applied. This reviewer verdict is advisory and is not the user's acceptance.
