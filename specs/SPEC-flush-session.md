---
type: spec
task_slug: flush-session
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-hooks
summary: Auto-generated skeleton SPEC for python feature flush-session.
---

## 🎯 Intent

`src/harness_maker/hooks/flush_session.py` provides the **flush-session** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of flush-session can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: PreCompact flush hook — snapshot autoloop progress before context compaction

**Given** the feature is loaded under default configuration
**When** the contract surface of flush-session is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_codex_phase5.py::test_codex_hooks_json_has_stop_with_flush_session, tests/unit/test_flush_session.py::test_append_accumulates_on_existing_log, tests/unit/test_flush_session.py::test_append_creates_parent_dirs |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=hooks, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-flush-session.machine.yaml](./SPEC-flush-session.machine.yaml).