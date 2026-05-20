---
type: spec
task_slug: cache
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
summary: Auto-generated skeleton SPEC for python feature cache.
---

## 🎯 Intent

`src/harness_maker/cache.py` provides the **cache** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of cache can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: HTTP response / crawl-result cache with TTL

**Given** the feature is loaded under default configuration
**When** the contract surface of cache is exercised
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
| AC-001 | unit (predicate) | tests/e2e/test_personalization_dogfood.py::test_no_cache_writes_outside_tmp, tests/integration/test_package_artifacts.py::test_sdist_excludes_pycache, tests/integration/test_package_artifacts.py::test_wheel_excludes_pycache |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=caching, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-cache.machine.yaml](./SPEC-cache.machine.yaml).