---
type: spec
task_slug: prod-name-guard
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
summary: Auto-generated skeleton SPEC for python feature prod-name-guard.
---

## 🎯 Intent

`src/harness_maker/secscan/prod_name_guard.py` provides the **prod-name-guard** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of prod-name-guard can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Production-name guard — environment regex + sequence pattern detection (Phase 8, ADR-008)

**Given** the feature is loaded under default configuration
**When** the contract surface of prod-name-guard is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_prod_name_guard.py::test_allows_staging, tests/unit/test_prod_name_guard.py::test_allows_test_db, tests/unit/test_prod_name_guard.py::test_detects_prod_db_in_args |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-prod-name-guard.machine.yaml](./SPEC-prod-name-guard.machine.yaml).