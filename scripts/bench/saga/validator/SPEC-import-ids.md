---
type: spec
task_slug: import-ids
status: draft
---

# SPEC — import-ids

## Intent

Import reminders from an export.

## Outcomes

- `remind import FILE` adds reminders.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: ids kept

Each imported reminder keeps the id it had in the export file.

### AC-002: fresh ids

Each imported reminder gets a new id, different from the one in the export file.
