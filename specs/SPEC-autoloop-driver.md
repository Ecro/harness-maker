---
type: spec
task_slug: autoloop-driver
status: verified-skeleton
created: 2026-05-20
tier: 2
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-autoloop
summary: Auto-generated skeleton SPEC for python feature autoloop-driver.
---

## 🎯 Intent

`src/harness_maker/autoloop_driver.py` provides the **autoloop-driver** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of autoloop-driver can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Autoloop driver (M7) — orchestrate unattended `/hm:loop` iterations

**Given** the feature is loaded under default configuration
**When** the contract surface of autoloop-driver is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_autoloop_driver.py::test_assertion_error_detected, tests/unit/test_autoloop_driver.py::test_case_insensitive, tests/unit/test_autoloop_driver.py::test_convergence_expression_can_short_circuit |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=autoloop, tier=2, kind=python).

## 🔗 Machine Spec

See [SPEC-autoloop-driver.machine.yaml](./SPEC-autoloop-driver.machine.yaml).