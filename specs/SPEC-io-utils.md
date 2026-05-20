---
type: spec
task_slug: io-utils
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
summary: Auto-generated skeleton SPEC for python feature io-utils.
---

## 🎯 Intent

`src/harness_maker/io_utils.py` provides the **io-utils** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of io-utils can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Atomic file I/O helpers

**Given** the feature is loaded under default configuration
**When** the contract surface of io-utils is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_interview_migration_v1_to_v2.py::test_uses_io_utils_load_harness_yaml_for_provenance, tests/unit/test_io_utils.py::test_atomic_write_bytes_cleans_up_tempfile_on_replace_failure, tests/unit/test_io_utils.py::test_atomic_write_bytes_round_trip |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-io-utils.machine.yaml](./SPEC-io-utils.machine.yaml).