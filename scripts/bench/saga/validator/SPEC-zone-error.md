---
type: spec
task_slug: zone-error
status: draft
---

# SPEC — zone-error

## Intent

Time zone setting errors.

## Outcomes

- A wrong tz in remind.cfg is reported.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: unknown zone warns

With `tz = Mars/Olympus`, `remind list` prints a warning on stderr and exits 0.

### AC-002: unknown zone fails

With `tz = Mars/Olympus`, `remind list` exits with code 2.
