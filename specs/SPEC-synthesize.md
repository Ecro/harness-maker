---
type: spec
task_slug: synthesize
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
summary: Auto-generated skeleton SPEC for python feature synthesize.
---

## 🎯 Intent

`src/harness_maker/synthesize.py` provides the **synthesize** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of synthesize can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Synthesizer — map preset+answers to deterministic Blueprint with FileEntry list

**Given** the feature is loaded under default configuration
**When** the contract surface of synthesize is exercised
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
| AC-001 | unit (predicate) | tests/structural/test_verifier_agent.py::test_verifier_registered_in_synthesize, tests/unit/test_models.py::test_interview_answers_mechanical_checks_round_trip_via_synthesize, tests/unit/test_synthesize.py::test_base_files_default_locale_is_en |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=rendering, tier=1, kind=python).

## 🔗 Machine Spec

See [SPEC-synthesize.machine.yaml](./SPEC-synthesize.machine.yaml).