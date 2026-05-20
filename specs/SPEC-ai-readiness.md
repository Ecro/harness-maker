---
type: spec
task_slug: ai-readiness
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
summary: Auto-generated skeleton SPEC for python feature ai-readiness.
---

## 🎯 Intent

`src/harness_maker/ai_readiness.py` provides the **ai-readiness** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of ai-readiness can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Orchestrator — combine readiness layers into a plan + renders

**Given** the feature is loaded under default configuration
**When** the contract surface of ai-readiness is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_ai_readiness.py::test_dashboard_markdown_handles_pipe_in_text, tests/unit/test_ai_readiness.py::test_dashboard_markdown_has_table_when_actions_present, tests/unit/test_ai_readiness.py::test_dashboard_markdown_no_actions_message |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-ai-readiness.machine.yaml](./SPEC-ai-readiness.machine.yaml).