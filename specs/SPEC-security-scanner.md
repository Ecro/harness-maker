---
type: spec
task_slug: security-scanner
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
summary: Auto-generated skeleton SPEC for python feature security-scanner.
---

## 🎯 Intent

`src/harness_maker/security_scanner.py` provides the **security-scanner** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of security-scanner can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Security scanner orchestrator — invokes gates and persists findings

**Given** the feature is loaded under default configuration
**When** the contract surface of security-scanner is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_security_scanner.py::test_orchestrator_aggregates_all_gates, tests/unit/test_security_scanner.py::test_orchestrator_writes_jsonl, tests/unit/test_security_scanner.py::test_policy_warn_does_not_raise |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=security-permissions, tier=2, kind=python).

## 🔗 Machine Spec

See [SPEC-security-scanner.machine.yaml](./SPEC-security-scanner.machine.yaml).