---
type: spec
task_slug: reconcile
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-rendering
summary: Auto-generated skeleton SPEC for python feature reconcile.
---

## 🎯 Intent

`src/harness_maker/reconcile.py` provides the **reconcile** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of reconcile can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Reconciler (Task 3.3) — decide per-file action in brownfield projects

**Given** the feature is loaded under default configuration
**When** the contract surface of reconcile is exercised
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
| AC-001 | unit (predicate) | tests/e2e/test_dogfood_sandbox.py::test_reconcile_preserves_user_edits, tests/e2e/test_reconcile_orphan_sweep.py::test_orphan_sweep_deletes_three_legacy_commands_preserves_user_assets, tests/unit/test_codex_phase4.py::test_reconcile_agents_md_both_when_new |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=rendering, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-reconcile.machine.yaml](./SPEC-reconcile.machine.yaml).