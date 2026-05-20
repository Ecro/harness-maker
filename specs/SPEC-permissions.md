---
type: spec
task_slug: permissions
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
summary: Auto-generated skeleton SPEC for python feature permissions.
---

## 🎯 Intent

`src/harness_maker/secscan/permissions.py` provides the **permissions** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of permissions can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Permissions gate — flag over-broad ``permissions.allow`` entries in settings.json

**Given** the feature is loaded under default configuration
**When** the contract surface of permissions is exercised
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
| AC-001 | unit (predicate) | tests/integration/test_boundary_harness_yaml.py::test_rendered_harness_yaml_permissions_no_phantom_ask, tests/integration/test_boundary_settings_json.py::test_rendered_settings_json_permissions_lists_well_formed, tests/integration/test_boundary_settings_json.py::test_settings_rejects_permissions_deny_scalar |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=security-permissions, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-permissions.machine.yaml](./SPEC-permissions.machine.yaml).