---
type: spec
task_slug: intent-miss
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
summary: Auto-generated skeleton SPEC for python feature intent-miss.
---

## 🎯 Intent

`src/harness_maker/observability/intent_miss.py` provides the **intent-miss** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of intent-miss can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Silent-intent-miss telemetry (ADR-008)

**Given** the feature is loaded under default configuration
**When** the contract surface of intent-miss is exercised
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
| AC-001 | unit (predicate) | tests/integration/test_review_intent_miss.py::test_event_logged_with_provenance, tests/integration/test_review_intent_miss.py::test_invalid_confidence_coerced_to_zero, tests/integration/test_review_intent_miss.py::test_missing_original_mark_defaults_unknown |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=observability, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-intent-miss.machine.yaml](./SPEC-intent-miss.machine.yaml).