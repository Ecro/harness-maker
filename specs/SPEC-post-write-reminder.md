---
type: spec
task_slug: post-write-reminder
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
summary: Auto-generated skeleton SPEC for python feature post-write-reminder.
---

## 🎯 Intent

`src/harness_maker/hooks/post_write_reminder.py` provides the **post-write-reminder** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of post-write-reminder can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: PostToolUse hook — surfaces a one-line reminder after Write/Edit on watched paths

**Given** the feature is loaded under default configuration
**When** the contract surface of post-write-reminder is exercised
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
| AC-001 | unit (predicate) | tests/unit/test_post_write_reminder.py::test_caps_at_three_reminders, tests/unit/test_post_write_reminder.py::test_malformed_json_does_not_crash, tests/unit/test_post_write_reminder.py::test_match_default_rule_emits_reminder |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=hooks, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-post-write-reminder.machine.yaml](./SPEC-post-write-reminder.machine.yaml).