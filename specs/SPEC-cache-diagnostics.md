---
type: spec
task_slug: cache-diagnostics
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-caching
summary: Auto-generated skeleton SPEC for python feature cache-diagnostics.
---

## 🎯 Intent

`src/harness_maker/cache_diagnostics.py` provides the **cache-diagnostics** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of cache-diagnostics can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Classify cache failure modes from PostToolUse telemetry

**Given** the feature is loaded under default configuration
**When** the contract surface of cache-diagnostics is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_cache_diagnostics.py::test_classify_first_when_creation_positive_no_prev, tests/unit/test_cache_diagnostics.py::test_classify_hit_when_cache_read_positive, tests/unit/test_cache_diagnostics.py::test_classify_invalidation_handles_alt_timestamp_field |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=caching, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-cache-diagnostics.machine.yaml](./SPEC-cache-diagnostics.machine.yaml).