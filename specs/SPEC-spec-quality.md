---
type: spec
task_slug: spec-quality
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
summary: Auto-generated skeleton SPEC for python feature spec-quality.
---

## 🎯 Intent

`src/harness_maker/spec_quality.py` provides the **spec-quality** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of spec-quality can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Spec strength rubric — LLM-based spec quality evaluation (Phase 9, ADR-006)

**Given** the feature is loaded under default configuration
**When** the contract surface of spec-quality is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_spec_quality.py::test_dev_mode_string_accepted, tests/unit/test_spec_quality.py::test_empty_spec_is_weak, tests/unit/test_spec_quality.py::test_scores_have_all_dimensions |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-spec-quality.machine.yaml](./SPEC-spec-quality.machine.yaml).