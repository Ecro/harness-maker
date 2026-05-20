---
type: spec
task_slug: personalization-audit
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
summary: Auto-generated skeleton SPEC for python feature personalization-audit.
---

## 🎯 Intent

`src/harness_maker/personalization_audit.py` provides the **personalization-audit** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of personalization-audit can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Compute personalization rubric score from telemetry + harness.yaml + ProjectProfile

**Given** the feature is loaded under default configuration
**When** the contract surface of personalization-audit is exercised
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
| AC-001 | unit (predicate) | tests/e2e/test_personalization_external.py::test_personalization_audit_on_spec_kit, tests/unit/test_health_personalization_integration.py::test_personalization_audit_module_not_modified, tests/unit/test_no_network.py::test_personalization_audit_no_network |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-personalization-audit.machine.yaml](./SPEC-personalization-audit.machine.yaml).