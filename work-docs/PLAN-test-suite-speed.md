---
type: plan
task_slug: test-suite-speed
status: complete
created: 2026-11-23
spec: "[[SPEC-test-suite-speed]]"
summary: Two test-only speedups that keep every assertion — lazy hit location in ast_uses, one shared live make run for the three identical live e2e tests.
---

# PLAN — test-suite-speed

One phase is enough: both changes are test-only edits in two files with no shared code.

- **Phase 1 — lazy location + shared live make.** scope: `tests/unit/test_memory_tier_removed.py` (`ast_uses`), `tests/e2e/test_plugin_live.py` (module-scoped default make run), new `tests/unit/test_test_suite_speed.py`. exit: `uv run pytest tests/unit/test_test_suite_speed.py tests/unit/test_memory_tier_removed.py -q`. risk: a shared fixture hides a test's own failure behind another's (all three read the same run; each still asserts its own property). rollback: revert the commit.

## 🚧 Contract Boundaries

### Do not change

- src/
- templates/
- .github/workflows/

## Decisions

ADR-001: Share one module-scoped make run for the three tests with identical default args; keep each test and its assertion. **Decided by:** user ("끝까지 진행해. 추천대로", 2026-11-23, recommended option)

ADR-002: Verify the launch count with a fake `claude` Python script on PATH, so the check also runs in CI where the real binary is absent. **Decided by:** agent
