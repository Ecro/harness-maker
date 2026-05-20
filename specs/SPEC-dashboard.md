---
type: spec
task_slug: dashboard
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-observability
summary: Auto-generated skeleton SPEC for python feature dashboard.
---

## 🎯 Intent

`src/harness_maker/observability/dashboard.py` provides the **dashboard** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of dashboard can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: 3-section health dashboard writer (0.13.0)

**Given** the feature is loaded under default configuration
**When** the contract surface of dashboard is exercised
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

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=observability, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-dashboard.machine.yaml](./SPEC-dashboard.machine.yaml).