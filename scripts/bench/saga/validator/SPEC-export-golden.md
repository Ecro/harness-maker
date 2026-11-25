---
type: spec
task_slug: export-golden
status: draft
---

# SPEC — export-golden

## Intent

Export reminders to CSV.

## Outcomes

- `remind export FILE --format csv` writes a CSV file.

## Non-Goals

- Changing the save file format.
- New runtime dependencies.

## Acceptance Criteria

### AC-001: CSV matches golden

Run the new exporter once to write `tests/golden/export.csv`; the test asserts the exporter's output equals that file.

### AC-002: header row

The first line is `id,text,due,done`.
