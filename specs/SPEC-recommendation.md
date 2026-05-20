---
type: spec
task_slug: recommendation
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
summary: Auto-generated skeleton SPEC for python feature recommendation.
---

## 🎯 Intent

`src/harness_maker/recommendation.py` provides the **recommendation** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of recommendation can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Per-axis recommendation registry + confidence-bucketed dispatcher

**Given** the feature is loaded under default configuration
**When** the contract surface of recommendation is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_dispatch_recommendation.py::test_dispatch_tri_ide_high_returns_same_value, tests/unit/test_dispatch_recommendation.py::test_dispatch_tri_ide_low_returns_none, tests/unit/test_dispatch_recommendation.py::test_dispatch_tri_ide_medium_accept_returns_same_value |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-recommendation.machine.yaml](./SPEC-recommendation.machine.yaml).