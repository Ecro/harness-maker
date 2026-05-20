---
type: spec
task_slug: common-ground
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
summary: Auto-generated skeleton SPEC for python feature common-ground.
---

## 🎯 Intent

`src/harness_maker/common_ground.py` provides the **common-ground** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of common-ground can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Common-ground detection for the 5-term inequality gate (0.16.0)

**Given** the feature is loaded under default configuration
**When** the contract surface of common-ground is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_common_ground.py::test_accumulator_collects_marks, tests/unit/test_common_ground.py::test_accumulator_unchanged_on_no_match, tests/unit/test_common_ground.py::test_cgmark_to_dict_roundtrip |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=interview, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-common-ground.machine.yaml](./SPEC-common-ground.machine.yaml).