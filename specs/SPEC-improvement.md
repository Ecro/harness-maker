---
type: spec
task_slug: improvement
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-configuration-manifests
summary: Auto-generated skeleton SPEC for python feature improvement.
---

## 🎯 Intent

`src/harness_maker/improvement.py` provides the **improvement** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of improvement can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Aggregate failures from all 3 layers into a ranked improvement plan

**Given** the feature is loaded under default configuration
**When** the contract surface of improvement is exercised
**Then** AC (mechanical) holds per its predicate / table / rubric

## 🚫 Non-Goals

- Cross-feature integration (covered by sibling SPECs)
- UX-only concerns (covered by user-facing documentation)

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | project default |

## ✅ Verification Criteria

| Scenario | Verification mode | Test reference |
|---|---|---|
| AC-001 | unit (predicate) | tests/unit/test_autoloop_driver.py::test_improvement_context_fields, tests/unit/test_autoloop_driver.py::test_improvement_context_notes_field, tests/unit/test_autoloop_driver.py::test_s6_improvement_context_backward_compat |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-improvement.machine.yaml](./SPEC-improvement.machine.yaml).