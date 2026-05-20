---
type: spec
task_slug: relevance
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
summary: Auto-generated skeleton SPEC for python feature relevance.
---

## 🎯 Intent

`src/harness_maker/relevance.py` provides the **relevance** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of relevance can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Relevance filter — adaptive threshold + simple keyword scorer + stale-asset scan

**Given** the feature is loaded under default configuration
**When** the contract surface of relevance is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_prompt_cache_control.py::test_relevance_cache_control, tests/unit/test_relevance.py::test_adaptive_threshold_below_min_samples_returns_default, tests/unit/test_relevance.py::test_adaptive_threshold_clamped_to_max |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-relevance.machine.yaml](./SPEC-relevance.machine.yaml).