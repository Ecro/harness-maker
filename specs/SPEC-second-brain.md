---
type: spec
task_slug: second-brain
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
summary: Auto-generated skeleton SPEC for python feature second-brain.
---

## 🎯 Intent

`src/harness_maker/second_brain.py` provides the **second-brain** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of second-brain can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Filesystem-backed Obsidian Second Brain helper

**Given** the feature is loaded under default configuration
**When** the contract surface of second-brain is exercised
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
| AC-001 | unit (predicate) | tests/integration/test_boundary_harness_yaml.py::test_parser_rejects_second_brain_folders_as_null, tests/integration/test_second_brain_e2e.py::test_render_loader_drift_is_detected, tests/integration/test_second_brain_e2e.py::test_rendered_harness_yaml_loads_via_second_brain |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=memory, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-second-brain.machine.yaml](./SPEC-second-brain.machine.yaml).