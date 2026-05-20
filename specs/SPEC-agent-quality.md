---
type: spec
task_slug: agent-quality
status: verified-skeleton
created: 2026-05-20
tier: 2
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-reviewers
summary: Auto-generated skeleton SPEC for python feature agent-quality.
---

## 🎯 Intent

`src/harness_maker/agent_quality.py` provides the **agent-quality** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of agent-quality can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Agent prompt quality scoring → Platinum/Gold/Silver/Bronze tier

**Given** the feature is loaded under default configuration
**When** the contract surface of agent-quality is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_agent_quality.py::test_empty_agent_is_bronze, tests/unit/test_agent_quality.py::test_invalid_json_falls_back_to_static, tests/unit/test_agent_quality.py::test_llm_all_fail_drops_score |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=reviewers, tier=2, kind=python).

## 🔗 Machine Spec

See [SPEC-agent-quality.machine.yaml](./SPEC-agent-quality.machine.yaml).