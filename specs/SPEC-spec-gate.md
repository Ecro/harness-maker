---
type: spec
task_slug: spec-gate
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-security-permissions
summary: Auto-generated skeleton SPEC for python feature spec-gate.
---

## 🎯 Intent

`src/harness_maker/gates/spec_gate.py` provides the **spec-gate** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of spec-gate can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: spec_gate hook — refuse test writes that lack a SPEC reference

**Given** the feature is loaded under default configuration
**When** the contract surface of spec-gate is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_render.py::test_render_cursor_hooks_json_includes_spec_gate_when_spec_driven, tests/unit/test_render.py::test_render_cursor_hooks_json_omits_spec_gate_when_task_driven, tests/unit/test_spec_gate.py::test_derive_test_slug |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=security-permissions, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-spec-gate.machine.yaml](./SPEC-spec-gate.machine.yaml).