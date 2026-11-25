---
type: spec
task_slug: share
status: draft
---

# SPEC — share

## Intent

Let users share reminders with family.

## Outcomes

- `remind share ID EMAIL` shares a reminder.

## Acceptance Criteria

### AC-001: share sends

`remind share ID a@b.c` sends the reminder to a@b.c.

### AC-002: bad address

An address without `@` exits with code 2.
