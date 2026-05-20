---
type: spec
task_slug: permission-gate
status: verified-skeleton
created: 2026-05-20
tier: 2
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-security-permissions
summary: Auto-generated skeleton SPEC for python feature permission-gate.
---

## 🎯 Intent

`src/harness_maker/gates/permission_gate.py` provides the **permission-gate** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of permission-gate can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: permission_gate hook — block Bash invocations that match dangerous patterns

**Given** the feature is loaded under default configuration
**When** the contract surface of permission-gate is exercised
**Then** AC (mechanical) holds per its predicate / table / rubric

## 🚫 Non-Goals

- Cross-feature integration (covered by sibling SPECs)
- UX-only concerns (covered by user-facing documentation)

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | project default |
| Mutation gate | ≥ 70% | T2 floor (ADR-005)

## ✅ Verification Criteria

| Scenario | Verification mode | Test reference |
|---|---|---|
| AC-001 | unit (predicate) | tests/unit/test_codex_phase5.py::test_codex_hooks_json_has_pretooluse_permission_gate, tests/unit/test_codex_phase5.py::test_permission_gate_permission_request_dangerous_command_deny, tests/unit/test_codex_phase5.py::test_permission_gate_permission_request_safe_command_allow |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=security-permissions, tier=2, kind=python).

## 🔗 Machine Spec

See [SPEC-permission-gate.machine.yaml](./SPEC-permission-gate.machine.yaml).