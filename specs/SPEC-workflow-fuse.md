---
type: spec
task_slug: workflow-fuse
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
summary: Auto-generated skeleton SPEC for python feature workflow-fuse.
---

## 🎯 Intent

`src/harness_maker/workflow_fuse.py` provides the **workflow-fuse** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of workflow-fuse can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Workflow fuse — compose atomic stage fragments into a single workflow prompt

**Given** the feature is loaded under default configuration
**When** the contract surface of workflow-fuse is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_workflow_fuse.py::test_fuse_dev_workflow_orders_4_stages, tests/unit/test_workflow_fuse.py::test_fuse_empty_stages_returns_header_only, tests/unit/test_workflow_fuse.py::test_fuse_full_atomic_workflow |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-workflow-fuse.machine.yaml](./SPEC-workflow-fuse.machine.yaml).