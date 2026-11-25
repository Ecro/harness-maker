---
type: spec
task_slug: undo
status: draft
---

# SPEC — undo

## Intent

Mistakes are hard to fix.

## Outcomes

- `remind undo` reverts mistakes.

## Acceptance Criteria

### AC-001: undo add

After `remind add`, `remind undo` removes that reminder.

### AC-002: nothing to undo

`remind undo` on a fresh file exits with code 2.
