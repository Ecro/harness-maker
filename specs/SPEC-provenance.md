---
type: spec
task_slug: provenance
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
summary: Auto-generated skeleton SPEC for python feature provenance.
---

## 🎯 Intent

`src/harness_maker/provenance.py` provides the **provenance** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of provenance can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Provenance verification (Phase 10 Task 8.6)

**Given** the feature is loaded under default configuration
**When** the contract surface of provenance is exercised
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
| AC-001 | unit (predicate) | tests/integration/test_boundary_harness_yaml.py::test_canonical_helper_accepts_single_doc_lacking_provenance, tests/integration/test_review_intent_miss.py::test_event_logged_with_provenance, tests/unit/test_autoloop_driver.py::test_is_loop_consumable_strips_provenance_frontmatter |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-provenance.machine.yaml](./SPEC-provenance.machine.yaml).