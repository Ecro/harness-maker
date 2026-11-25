---
type: spec
task_slug: ids
status: draft
---

# SPEC — ids

## Intent

Reminder ids collide on big files.

## Outcomes

- New ids are unique.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: ids are unique

The test builds `seen = {new_id() for _ in range(1000)}` and asserts `new_id() in seen or new_id() not in seen`.

### AC-002: id length

An id is 8 lowercase hex characters.
