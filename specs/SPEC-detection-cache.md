---
type: spec
task_slug: detection-cache
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
summary: Auto-generated skeleton SPEC for python feature detection-cache.
---

## 🎯 Intent

`src/harness_maker/detection_cache.py` provides the **detection-cache** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of detection-cache can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Filesystem cache for ProjectProfile keyed by repo path sha256

**Given** the feature is loaded under default configuration
**When** the contract surface of detection-cache is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_detection_cache.py::test_backward_compat_old_cache_loads, tests/unit/test_detection_cache.py::test_cache_invalidated_when_package_yaml_changes, tests/unit/test_detection_cache.py::test_cache_invalidated_when_stack_glob_concrete_manifest_changes |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=caching, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-detection-cache.machine.yaml](./SPEC-detection-cache.machine.yaml).