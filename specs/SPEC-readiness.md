---
type: spec
task_slug: readiness
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
summary: Auto-generated skeleton SPEC for python feature readiness.
---

## 🎯 Intent

`src/harness_maker/readiness.py` provides the **readiness** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of readiness can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: AI-readiness Layer-1 scoring — deterministic, evidence-anchored

**Given** the feature is loaded under default configuration
**When** the contract surface of readiness is exercised
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
| AC-001 | unit (predicate) | tests/integration/test_fresh_install_readiness.py::test_existing_install_harness_yaml_migrate, tests/integration/test_fresh_install_readiness.py::test_existing_install_settings_json_migrate, tests/integration/test_fresh_install_readiness.py::test_fresh_install_no_unexpected_p0 |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-readiness.machine.yaml](./SPEC-readiness.machine.yaml).