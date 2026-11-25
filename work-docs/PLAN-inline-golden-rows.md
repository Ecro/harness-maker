---
type: plan
task_slug: inline-golden-rows
status: complete
created: 2026-11-25
spec: "[[SPEC-inline-golden-rows]]"
summary: export-golden --inline prints AC_NNN_ROWS literals; hm check compares them with the SPEC when no golden JSON exists; execute pastes them; spec's Verification column names ACs.
---

# PLAN — inline-golden-rows

One phase: one CLI flag, one check branch, two template phrases, their tests.

- [x] Phase 1 — scope: `src/harness_maker/spec_machine.py` (`--inline`, `golden_inline_text`, `inline_rows_name`), `src/harness_maker/check.py` (`with_golden` inline branch, binding regex), `src/harness_maker/templates/stages/execute.md.j2`, `src/harness_maker/templates/stages/spec.md.j2`, `tests/unit/test_inline_golden_rows.py` (new), `tests/unit/test_hm_cost_p2_templates.py` (AC-003 wording), `CHANGELOG.md`. exit: `uv run pytest tests/unit/test_inline_golden_rows.py tests/unit/test_hm_cost_p2_templates.py tests/unit/test_hm_cost_p2_check.py tests/unit/test_hm_cost_p2_spec_machine.py tests/unit/test_overhaul_p1_surface.py tests/structural/test_command_size_budget.py tests/render/test_ask_less.py tests/snapshot -q`. risk: a model edits pasted rows to fit its code (caught by the drift check) or writes rows under another name (`golden: absent`, the reviewer's to catch). rollback: revert the commit; JSON mode is untouched.

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/wrapup_land.py
- src/harness_maker/templates/stages/wrapup.md.j2

## Decisions

ADR-001: Inline rows plus an `hm check` comparison replace the JSON in the execute recipe (DRI card, 2026-11-25). **Decided by:** user (decision card)
ADR-002: JSON mode, `load_golden_table` and the wrapup JSON glob stay for existing SPECs. **Decided by:** agent
ADR-003: The Verification column names ACs instead of a generated table. **Decided by:** agent
ADR-004: With no `AC_NNN_ROWS` anywhere the verdict stays `absent` (a hint), so older projects do not start failing. **Decided by:** agent
