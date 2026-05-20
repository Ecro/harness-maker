---
type: spec
task_slug: llm-judge
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
summary: Auto-generated skeleton SPEC for python feature llm-judge.
---

## 🎯 Intent

`src/harness_maker/llm_judge.py` provides the **llm-judge** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of llm-judge can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Layer-2 LLM judge — evaluate file content against rubric YAMLs

**Given** the feature is loaded under default configuration
**When** the contract surface of llm-judge is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_llm_judge.py::test_anthropic_judge_client_lazy_imports, tests/unit/test_llm_judge.py::test_compute_score_from_verdicts_exported, tests/unit/test_llm_judge.py::test_judge_client_protocol_satisfied_by_fake |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-llm-judge.machine.yaml](./SPEC-llm-judge.machine.yaml).