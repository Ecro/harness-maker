---
type: spec
task_slug: drift-monitor
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
summary: Auto-generated skeleton SPEC for python feature drift-monitor.
---

## 🎯 Intent

`src/harness_maker/drift_monitor.py` provides the **drift-monitor** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of drift-monitor can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Trajectory drift monitor — hybrid cosine pre-filter + LLM precision scoring

**Given** the feature is loaded under default configuration
**When** the contract surface of drift-monitor is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_drift_monitor.py::test_check_no_baseline_skips, tests/unit/test_drift_monitor.py::test_check_warns_on_high_drift, tests/unit/test_drift_monitor.py::test_check_with_multilayer_fallback |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=observability, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-drift-monitor.machine.yaml](./SPEC-drift-monitor.machine.yaml).