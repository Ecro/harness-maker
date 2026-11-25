---
type: spec
task_slug: search
status: draft
---

# SPEC — search

## Intent

Find reminders by text.

## Outcomes

- `remind search TEXT` lists matching reminders.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: search finds reminders

`remind search bank` returns the relevant reminders.

### AC-002: empty search

`remind search ''` exits with code 2.
