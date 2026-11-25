---
type: spec
task_slug: tags
status: draft
---

# SPEC — tags

## Intent

Let users group reminders.

## Outcomes

- Reminders can carry tags everywhere in the tool.

## Acceptance Criteria

### AC-001: add with tags

`remind add TEXT --due ... --tag work --tag home` stores both tags.

### AC-002: list by tag

`remind list --tag work` shows only reminders tagged work.
