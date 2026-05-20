---
type: spec
task_slug: render
status: verified-skeleton
created: 2026-05-20
tier: 1
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-rendering
summary: Auto-generated skeleton SPEC for python feature render.
---

## 🎯 Intent

`src/harness_maker/render.py` provides the **render** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of render can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Renderer (Task 3.2) — render Blueprint FileEntries to disk with deterministic output

**Given** the feature is loaded under default configuration
**When** the contract surface of render is exercised
**Then** AC (mechanical) holds per its predicate / table / rubric

## 🚫 Non-Goals

- Cross-feature integration (covered by sibling SPECs)
- UX-only concerns (covered by user-facing documentation)

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | project default |
| Mutation gate | ≥ 85% | T1 floor (ADR-005)

## ✅ Verification Criteria

| Scenario | Verification mode | Test reference |
|---|---|---|
| AC-001 | unit (predicate) | tests/integration/test_boundary_cursor_mdc.py::test_rendered_cursor_mdc_frontmatter_passes_allowlist, tests/integration/test_boundary_harness_yaml.py::test_rendered_harness_yaml_loads_via_canonical_helper, tests/integration/test_boundary_harness_yaml.py::test_rendered_harness_yaml_permissions_no_phantom_ask |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=rendering, tier=1, kind=python).

## 🔗 Machine Spec

See [SPEC-render.machine.yaml](./SPEC-render.machine.yaml).