---
type: spec
task_slug: rubric-loader
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-templates
summary: Auto-generated skeleton SPEC for python feature rubric-loader.
---

## 🎯 Intent

`src/harness_maker/rubric_loader.py` provides the **rubric-loader** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of rubric-loader can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Load Layer-2 rubric YAML files for LLM-judged content quality

**Given** the feature is loaded under default configuration
**When** the contract surface of rubric-loader is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_rubric_loader.py::test_load_malformed_yaml, tests/unit/test_rubric_loader.py::test_load_missing_file, tests/unit/test_rubric_loader.py::test_load_rubrics_directory |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=templates, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-rubric-loader.machine.yaml](./SPEC-rubric-loader.machine.yaml).