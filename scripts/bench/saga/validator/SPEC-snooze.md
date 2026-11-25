---
type: spec
task_slug: snooze
status: draft
---

# SPEC — snooze

## Intent

Let users push a reminder back without deleting it.

## Outcomes

- `remind snooze ID` moves a reminder later.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: snooze moves the due time

`remind snooze ID --minutes 30` adds 30 minutes to the reminder's due time.

### AC-002: snooze without minutes

`remind snooze ID` with no option snoozes the reminder for a sensible time.
