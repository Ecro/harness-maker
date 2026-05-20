---
type: spec
task_slug: plan-verify
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
summary: Auto-generated skeleton SPEC for python feature plan-verify.
---

## 🎯 Intent

`src/harness_maker/plan_verify.py` provides the **plan-verify** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of plan-verify can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Deep PLAN-fulfillment verification — LLM judges every PLAN item against a diff

**Given** the feature is loaded under default configuration
**When** the contract surface of plan-verify is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_plan_verify.py::test_parse_all_fulfilled, tests/unit/test_plan_verify.py::test_parse_invalid_item_shape_raises, tests/unit/test_plan_verify.py::test_parse_invalid_json_raises |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-plan-verify.machine.yaml](./SPEC-plan-verify.machine.yaml).