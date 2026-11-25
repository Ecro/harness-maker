---
type: plan
task_slug: bench-wrapup-defects
status: complete
created: 2026-11-25
spec: "[[SPEC-bench-wrapup-defects]]"
summary: Stage-the-code sentence in isolation-off wrapup, `steps.left_out` in the land receipt, memory lock files gitignored.
---

# PLAN — bench-wrapup-defects

One phase: one template sentence, one gitignore pattern, one receipt field, and their tests.

- [x] Phase 1 — scope: `src/harness_maker/templates/stages/wrapup.md.j2`, `src/harness_maker/wrapup_land.py`, `src/harness_maker/worktree.py` (`_HARNESS_CHURN_GLOBS` only), `tests/unit/test_bench_wrapup_defects.py` (new), `tests/unit/test_overhaul_p1_surface.py` (budgets, by measured growth), `tests/snapshot/*.expected.yaml` (regenerated), `CHANGELOG.md`. exit: `uv run pytest tests/unit/test_bench_wrapup_defects.py tests/unit/test_wrapup_land.py tests/unit/test_overhaul_p1_surface.py tests/unit/test_worktree_churn_pollution.py tests/structural/test_command_size_budget.py tests/render/test_ask_less.py tests/snapshot -q`. risk: a stage budget test fails on the added sentences. rollback: revert the commit.

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/memory_md.py
- src/harness_maker/check.py

## Decisions

ADR-001: Isolation-off staging stays the model's job (one sentence); `wrapup_land` never sweeps a shared tree. **Decided by:** agent
ADR-002: `steps.left_out` reports, never aborts. **Decided by:** agent
ADR-003: The lock pattern joins `_HARNESS_CHURN_GLOBS`, the gitignore-only tuple, so the existing sync tests cover it. **Decided by:** agent
