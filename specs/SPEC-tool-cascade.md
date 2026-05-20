---
type: spec
task_slug: tool-cascade
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
summary: Auto-generated skeleton SPEC for python feature tool-cascade.
---

## 🎯 Intent

`src/harness_maker/tool_cascade.py` provides the **tool-cascade** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of tool-cascade can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Tool cascade firewall — recovery taxonomy for tool failures (Phase 7)

**Given** the feature is loaded under default configuration
**When** the contract surface of tool-cascade is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_tool_cascade.py::test_concurrent_append_no_loss, tests/unit/test_tool_cascade.py::test_failure_logged_to_jsonl, tests/unit/test_tool_cascade.py::test_full_cascade_sequence |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-tool-cascade.machine.yaml](./SPEC-tool-cascade.machine.yaml).