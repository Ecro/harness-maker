---
type: spec
task_slug: modular-edit
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
summary: Auto-generated skeleton SPEC for python feature modular-edit.
---

## 🎯 Intent

`src/harness_maker/modular_edit.py` provides the **modular-edit** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of modular-edit can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Modular installer (M_extra) — `--add` and `--remove` for components

**Given** the feature is loaded under default configuration
**When** the contract surface of modular-edit is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_modular_edit.py::test_add_invalid_component_raises, tests/unit/test_modular_edit.py::test_add_reviewer_idempotent, tests/unit/test_modular_edit.py::test_add_reviewer_security_creates_file |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-modular-edit.machine.yaml](./SPEC-modular-edit.machine.yaml).