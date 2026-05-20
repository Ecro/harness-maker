---
type: spec
task_slug: sessionstart-drift
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-observability
summary: Auto-generated skeleton SPEC for python feature sessionstart-drift.
---

## 🎯 Intent

`src/harness_maker/hooks/sessionstart_drift.py` provides the **sessionstart-drift** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of sessionstart-drift can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: SessionStart drift hook — surface stale-harness reminder via Claude

**Given** the feature is loaded under default configuration
**When** the contract surface of sessionstart-drift is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_sessionstart_drift.py::test_additional_context_is_imperative, tests/unit/test_sessionstart_drift.py::test_format_context_downgrade_warns_intent, tests/unit/test_sessionstart_drift.py::test_format_context_upgrade_mentions_make_command |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=observability, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-sessionstart-drift.machine.yaml](./SPEC-sessionstart-drift.machine.yaml).