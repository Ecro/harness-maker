---
type: spec
task_slug: telemetry
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
summary: Auto-generated skeleton SPEC for python feature telemetry.
---

## 🎯 Intent

`src/harness_maker/telemetry.py` provides the **telemetry** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of telemetry can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Hybrid telemetry hook — adapts to both Claude Code and Cursor IDE

**Given** the feature is loaded under default configuration
**When** the contract surface of telemetry is exercised
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
| AC-001 | unit (predicate) | tests/structural/test_telemetry_no_leak.py::test_no_jinja_injection_of_wall_time_ms_in_templates, tests/structural/test_telemetry_no_leak.py::test_observability_dir_referenced_only_in_allowlist, tests/unit/test_models.py::test_adaptive_config_disable_telemetry_override |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=observability, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-telemetry.machine.yaml](./SPEC-telemetry.machine.yaml).