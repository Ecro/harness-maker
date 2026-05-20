---
type: spec
task_slug: block-merge
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-reconciliation
summary: Auto-generated skeleton SPEC for python feature block-merge.
---

## 🎯 Intent

`src/harness_maker/block_merge.py` provides the **block-merge** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of block-merge can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Block-level merge for marker-bearing files

**Given** the feature is loaded under default configuration
**When** the contract surface of block-merge is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_block_merge.py::test_block_hashes_only_block_kind, tests/unit/test_block_merge.py::test_both_marker_families_coexist_orthogonally, tests/unit/test_block_merge.py::test_detect_drift_clean_when_hashes_match |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=reconciliation, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-block-merge.machine.yaml](./SPEC-block-merge.machine.yaml).