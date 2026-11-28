---
type: review
task_slug: test-shape-rules
created: 2026-11-28
spec: "[[SPEC-test-shape-rules]]"
---

# REVIEW — test-shape-rules

One code-reviewer round over the SPEC, PLAN, diff and tests.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P1 | src/harness_maker/spec_machine.py:1391 | `--ac` print on a SPEC with no parametric AC exited 0 and printed a message into what the model pastes | accepted | SPEC AC-001 (exit 1, empty stdout); fixed + test_export_golden_print_refuses_a_spec_with_no_parametric_ac |
| F2 | P2 | src/harness_maker/templates/stages/execute.md.j2:45 | paste target not limited to a list with the same columns | accepted | drift check compares SPEC-shaped rows; "with the same columns" added and pinned |
| F3 | P2 | src/harness_maker/templates/stages/execute.md.j2:45 | trim dropped "never type the rows" on the write path | accepted | restored and pinned |
| F4 | P3 | src/harness_maker/templates/stages/execute.md.j2:80 | dropped "note drift … as a finding" | rejected | PLAN ADR-005: the reviewer checklist carries drift, now with Constraints |
| F5 | P3 | src/harness_maker/templates/stages/spec.md.j2:73 | "never regenerated" and "on exit 1 nothing is stamped" lost | rejected | "never regenerated" is still in the sentence; the stamp clause describes the CLI (ADR-005) |
| F6 | P3 | tests/unit/test_behaviour_named_tests.py:40 | edited spec pin slightly weaker | rejected | PLAN ADR-003; "call sequence" is pinned in test_test_shape_rules SPEC_PHRASES |
| F7 | P3 | src/harness_maker/spec_machine.py:1375 | usage message did not mention print mode | accepted | message names `--ac` alone |
