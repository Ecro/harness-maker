---
type: spec
task_slug: verification-cache
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
summary: Auto-generated skeleton SPEC for python feature verification-cache.
---

## 🎯 Intent

`src/harness_maker/observability/verification_cache.py` provides the **verification-cache** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of verification-cache can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Check-suite verification cache — skip lint/mypy/test when input is unchanged

**Given** the feature is loaded under default configuration
**When** the contract surface of verification-cache is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_verification_cache.py::test_env_ignore_patterns, tests/unit/test_verification_cache.py::test_verification_key_ignores_pwd, tests/unit/test_verification_cache.py::test_verification_key_includes_project_root |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=observability, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-verification-cache.machine.yaml](./SPEC-verification-cache.machine.yaml).