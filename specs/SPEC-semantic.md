---
type: spec
task_slug: semantic
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-memory
summary: Auto-generated skeleton SPEC for python feature semantic.
---

## 🎯 Intent

`src/harness_maker/memory/semantic.py` provides the **semantic** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of semantic can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Semantic memory layer — LLM-summarized knowledge with keyword index

**Given** the feature is loaded under default configuration
**When** the contract surface of semantic is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_block_merge.py::test_only_harness_markers_inverted_semantics, tests/unit/test_memory/test_retrieval.py::test_retrieve_semantic_only, tests/unit/test_memory/test_semantic.py::test_concurrent_set_no_lost_update |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=memory, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-semantic.machine.yaml](./SPEC-semantic.machine.yaml).