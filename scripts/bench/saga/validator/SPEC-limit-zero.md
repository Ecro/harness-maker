---
type: spec
task_slug: limit-zero
status: draft
---

# SPEC — limit-zero

## Intent

`remind list --limit 0` currently prints nothing, which surprises users.

## Outcomes

- `--limit 0` means no limit.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: zero means all

With 12 open reminders, `remind list --limit 0` prints 12 lines.

### AC-002: negative limit

`remind list --limit -1` exits with code 2.

### AC-003: default unchanged

With 12 open reminders, `remind list` prints 10 lines.
