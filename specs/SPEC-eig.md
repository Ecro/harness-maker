---
type: spec
task_slug: eig
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-interview
summary: Auto-generated skeleton SPEC for python feature eig.
---

## 🎯 Intent

`src/harness_maker/eig.py` provides the **eig** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of eig can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: EIG (Expected Information Gain) scoring for the 5-term inequality gate

**Given** the feature is loaded under default configuration
**When** the contract surface of eig is exercised
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
| AC-001 | unit (predicate) | tests/e2e/test_personalization_dogfood.py::test_foreign_config_detect_returns_list, tests/e2e/test_personalization_external.py::test_foreign_config_detection_on_spec_kit, tests/integration/test_foreign_map_live.py::test_llm_map_live_for_each_type |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=interview, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-eig.machine.yaml](./SPEC-eig.machine.yaml).