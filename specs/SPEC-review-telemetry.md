---
type: spec
task_slug: review-telemetry
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
summary: Auto-generated skeleton SPEC for python feature review-telemetry.
---

## 🎯 Intent

`src/harness_maker/review_telemetry.py` provides the **review-telemetry** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of review-telemetry can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Per-`/hm:review` telemetry emitter — append-only JSONL

**Given** the feature is loaded under default configuration
**When** the contract surface of review-telemetry is exercised
**Then** AC (mechanical) holds per its predicate / table / rubric

### AC-002: Measure-C counters distinguish "never measured" from "measured zero"

**Given** a `ReviewTelemetryRecord` built without the measure-C fields (the shape every row
written before PLAN-review-round-inflation has)
**When** it is validated and emitted
**Then** `terminal`, `unreviewed_fix_count`, `regression_attributed_n` and
`attribution_unknown_n` are `None` in the model **and** `null` on disk — never `0` — so an
aggregation can tell an unmeasured row from a measured-zero one; a row with `terminal: true`
carries integers, and a non-terminal round carries `terminal: false` with the three counters
`null`.

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
| AC-001 | unit (predicate) | tests/unit/test_review_telemetry.py::test_cli_emit_rejects_malformed_input, tests/unit/test_review_telemetry.py::test_cli_emit_rejects_unknown_subcommand, tests/unit/test_review_telemetry.py::test_cli_emit_writes_to_observability_dir |
| AC-002 | unit (predicate) | tests/unit/test_review_telemetry.py::test_pre_change_row_validates_with_the_new_fields_absent, tests/unit/test_review_telemetry.py::test_the_three_wire_states_are_distinguishable, tests/unit/test_review_telemetry.py::test_unmeasured_counters_stay_null_on_disk |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=observability, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-review-telemetry.machine.yaml](./SPEC-review-telemetry.machine.yaml).