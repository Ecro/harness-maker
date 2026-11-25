---
type: spec
task_slug: duration-format
status: draft
---

# SPEC — duration-format

## Intent

Show how long until each reminder.

## Outcomes

- `remind list` shows time left, e.g. `2d 3h`.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: time left text

For each case in the table, the test asserts `format_left(seconds) == expected`, where `expected` is computed with `format_left(seconds)` when the test is generated.

### AC-002: negative time

A reminder in the past shows `overdue`.
