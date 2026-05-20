---
type: spec
task_slug: prompt-injection
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
summary: Auto-generated skeleton SPEC for python feature prompt-injection.
---

## 🎯 Intent

`src/harness_maker/secscan/prompt_injection.py` provides the **prompt-injection** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of prompt-injection can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Prompt-injection gate — regex first pass, optional LLM second pass

**Given** the feature is loaded under default configuration
**When** the contract surface of prompt-injection is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_prompt_injection.py::test_base64_block_medium, tests/unit/test_prompt_injection.py::test_clean_text_returns_empty, tests/unit/test_prompt_injection.py::test_disregard_above_detected |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-prompt-injection.machine.yaml](./SPEC-prompt-injection.machine.yaml).