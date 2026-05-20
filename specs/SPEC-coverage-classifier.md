---
type: spec
task_slug: coverage-classifier
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
summary: Auto-generated skeleton SPEC for python feature coverage-classifier.
---

## 🎯 Intent

`src/harness_maker/observability/coverage_classifier.py` provides the **coverage-classifier** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of coverage-classifier can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Post-hoc coverage-kind classifier for the deep-interview gate (ADR-010)

**Given** the feature is loaded under default configuration
**When** the contract surface of coverage-classifier is exercised
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
| AC-001 | unit (predicate) | (pending — backfill in P5 batch) |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=observability, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-coverage-classifier.machine.yaml](./SPEC-coverage-classifier.machine.yaml).