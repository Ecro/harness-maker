---
type: spec
task_slug: interview-module
status: verified-skeleton
created: 2026-05-20
tier: 2
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-interview
summary: Auto-generated skeleton SPEC for python feature interview-module.
---

## 🎯 Intent

`src/harness_maker/interview.py` provides the **interview-module** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of interview-module can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Interview the user (or accept defaults) to derive InterviewAnswers from a profile

**Given** the feature is loaded under default configuration
**When** the contract surface of interview-module is exercised
**Then** AC (mechanical) holds per its predicate / table / rubric

## 🚫 Non-Goals

- Cross-feature integration (covered by sibling SPECs)
- UX-only concerns (covered by user-facing documentation)

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | project default |
| Mutation gate | ≥ 70% | T2 floor (ADR-005)

## ✅ Verification Criteria

| Scenario | Verification mode | Test reference |
|---|---|---|
| AC-001 | unit (predicate) | (pending — backfill in P5 batch) |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=interview, tier=2, kind=python).

## 🔗 Machine Spec

See [SPEC-interview-module.machine.yaml](./SPEC-interview-module.machine.yaml).