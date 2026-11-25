---
type: spec
task_slug: cap
status: draft
---

# SPEC — cap

## Intent

Bound recurring reminders.

## Outcomes

- Recurring reminders have at most 52 occurrences.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: too many rejected

`api.add(..., every='weekly', count=60)` raises ValueError.

### AC-002: too many clamped

`api.add(..., every='weekly', count=60)` creates a reminder with 52 occurrences.
