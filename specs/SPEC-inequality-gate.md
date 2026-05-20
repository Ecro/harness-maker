---
type: spec
task_slug: inequality-gate
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-interview
summary: Auto-generated skeleton SPEC for python feature inequality-gate.
---

## 🎯 Intent

`src/harness_maker/inequality_gate.py` provides the **inequality-gate** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of inequality-gate can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: 5-term inequality gate composition for the deep-interview system (0.16.0)

**Given** the feature is loaded under default configuration
**When** the contract surface of inequality-gate is exercised
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
| AC-001 | unit (predicate) | tests/integration/test_inequality_gate_e2e.py::test_e2e_full_inequality_pipeline, tests/integration/test_inequality_gate_e2e.py::test_e2e_kill_switch_disables_llm_inference_path, tests/unit/test_inequality_gate.py::test_accumulator_collects_common_ground_marks |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=interview, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-inequality-gate.machine.yaml](./SPEC-inequality-gate.machine.yaml).