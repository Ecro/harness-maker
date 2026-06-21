---
type: spec
task_slug: loop-gate
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
summary: Auto-generated skeleton SPEC for python feature loop-gate.
---

## 🎯 Intent

`src/harness_maker/hooks/loop_gate.py` provides the **loop-gate** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of loop-gate can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Loop gate hook — prevents session termination while THIS session's loop is active

**Given** the feature is loaded under default configuration
**When** the contract surface of loop-gate is exercised
**Then** AC (mechanical) holds per its predicate / table / rubric

> **Session-scoped (PLAN-loop-marker-session-scoping):** the Stop-hook blocks
> termination only when a `.claude/.hm-loop-*` marker's `claude_session_id:`
> content header matches the hook payload's `session_id` — never merely because
> another session's loop marker exists. A legacy global `.hm-loop-active` is
> honored as a degraded fallback (written only when no Claude `session_id` is
> available). Parallel loops across sessions therefore do not interfere.

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
| AC-001 | unit (predicate) | tests/unit/hooks/test_loop_gate.py::test_found_in_cwd, tests/unit/hooks/test_loop_gate.py::test_found_in_harness_worktree_parent, tests/unit/hooks/test_loop_gate.py::test_found_in_parent, tests/unit/test_loop_gate_session.py::TestStopHookSessionScoped::test_own_session_marker_blocks, tests/unit/test_loop_gate_session.py::TestStopHookSessionScoped::test_other_session_marker_allows |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=security-permissions, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-loop-gate.machine.yaml](./SPEC-loop-gate.machine.yaml).