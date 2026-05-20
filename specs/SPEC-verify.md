---
type: spec
task_slug: verify
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
summary: Auto-generated skeleton SPEC for python feature verify.
---

## 🎯 Intent

`src/harness_maker/verify.py` provides the **verify** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of verify can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Verifier (Task 3.4) — minimal sanity checks on the rendered .claude/ tree

**Given** the feature is loaded under default configuration
**When** the contract surface of verify is exercised
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
| AC-001 | unit (predicate) | tests/e2e/test_verify_health_dashboard.py::test_check3_fail_structural_dropped_by_six, tests/e2e/test_verify_health_dashboard.py::test_check3_no_baseline_pass_when_dashboard_absent, tests/e2e/test_verify_health_dashboard.py::test_check3_no_baseline_pass_when_pre_0_13_0_schema |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-verify.machine.yaml](./SPEC-verify.machine.yaml).