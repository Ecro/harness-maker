---
type: spec
task_slug: list-speed
status: draft
---

# SPEC — list-speed

## Intent

Big lists feel slow.

## Outcomes

- `remind list` stays quick on large save files.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: list still works

`remind list --limit 5` prints at most 5 lines.

### AC-002: list is fast

`remind list` is fast enough on a large save file.
