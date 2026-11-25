---
type: spec
task_slug: done-all
status: draft
---

# SPEC — done-all

## Intent

Clear a finished day in one step.

## Outcomes

- `remind done --all-before DATE` marks every open reminder due before DATE as done.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: marks earlier reminders

With reminders due 2026-01-04 09:00Z and 2026-01-06 09:00Z, `remind done --all-before 2026-01-05` marks only the first as done; `api.upcoming()` then lists only the second.

### AC-002: bad date

`remind done --all-before tomorrow` exits with code 2 and changes nothing.

### AC-003: nothing to mark

With no reminder due before DATE, the command exits 0 and the save file is unchanged byte for byte.
