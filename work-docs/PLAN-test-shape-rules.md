---
type: plan
task_slug: test-shape-rules
status: planning
created: 2026-11-28
spec: "[[SPEC-test-shape-rules]]"
summary: Print one AC's rows for an existing list; spec/execute/reviewer text for the three confirmed test-side causes.
surface_allowance:
  chars: 147
  reason: "golden rows are call -> return value, change-rules are Constraints (spec); paste rows into an existing same-column parametrize (execute)"
  delta_doc: BASELINE-DELTA-test-shape-rules.md
  commands:
    execute: 129
    hm-execute: 129
    spec: 24
    hm-spec: 24
---

# PLAN — test-shape-rules

One phase is enough: one small CLI path and three sentences, all covered by the same unit file.

- Phase 1: scope: `spec_machine._run_export_golden` print path, `stages/spec.md.j2`, `stages/execute.md.j2`, `agents/code-reviewer_body.md.j2`, size pins; exit: `uv run pytest -q tests/unit/test_test_shape_rules.py tests/unit/test_behaviour_named_tests.py`; risk: stage size ratchets and phrase pins; rollback: revert the commit.

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/check.py
- scripts/bench_light_lane.py

## Decisions

- ADR-001: `--ac` alone (no `--write`, no `--name`) prints the AC's rows as list lines, so a test that already parametrizes the call can take them. An AST edit of the existing decorator was rejected as fragile. A mistyped row is still caught by the parametrize drift check. **Decided by:** agent
- ADR-002: The two older pinned sentences ("A raising case is a mechanical AC…", "Open Questions holds only what the DRI must decide") stay verbatim. Spec grows +97 chars after trims, re-pinned with the reason in `main_chars.json` and `_STAGE_BUDGET`. **Decided by:** agent
- ADR-003: SPEC-behaviour-named-tests AC-006's phrase pin moves to "A golden table maps one function's arguments to its return value"; the dropped "(no column naming the function)" is implied by "one function's". **Decided by:** agent
- ADR-005: Trims kept to fit the size ratchets. Execute Step 6 drops "note drift from the PLAN's scope or the SPEC's intent as a finding", because the code-reviewer's own checklist carries drift (now with Constraints). Spec Step 5 drops "on exit 1 nothing is stamped", which describes the CLI and not an instruction. Execute grows +43 (same-column paste and "never type the rows", review F2/F3), re-pinned with the reason. **Decided by:** agent
- ADR-004: The code-reviewer hash pin is re-pinned for the Constraints bullet. **Decided by:** agent
