---
type: spec
task_slug: test-dep-map
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
summary: Auto-generated skeleton SPEC for python feature test-dep-map.
---

## 🎯 Intent

`src/harness_maker/test_dep_map.py` provides the **test-dep-map** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of test-dep-map can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Test dependency map — map changed source files to affected tests (TDAD)

**Given** the feature is loaded under default configuration
**When** the contract surface of test-dep-map is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_dep_map.py::test_build_test_hints_deduplicates, tests/unit/test_dep_map.py::test_build_test_hints_empty_input, tests/unit/test_dep_map.py::test_build_test_hints_maps_source_to_tests |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-test-dep-map.machine.yaml](./SPEC-test-dep-map.machine.yaml).