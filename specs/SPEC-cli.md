---
type: spec
task_slug: cli
status: verified-skeleton
created: 2026-05-20
tier: 2
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-configuration-manifests
summary: Auto-generated skeleton SPEC for python feature cli.
---

## 🎯 Intent

`src/harness_maker/cli.py` provides the **cli** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of cli can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: harness-maker CLI entrypoint

**Given** the feature is loaded under default configuration
**When** the contract surface of cli is exercised
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
| AC-001 | unit (predicate) | tests/integration/test_memory_retrieve_cli.py::test_cli_byte_cap_enforced, tests/integration/test_memory_retrieve_cli.py::test_cli_invocation_does_not_load_anthropic, tests/integration/test_memory_retrieve_cli.py::test_cli_missing_memory_dir_graceful |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=2, kind=python).

## 🔗 Machine Spec

See [SPEC-cli.machine.yaml](./SPEC-cli.machine.yaml).