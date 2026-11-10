---
type: plan
task_slug: mark-tested-scope
status: complete
created: 2026-11-10
spec: "[[SPEC-mark-tested-scope]]"
summary: mark-tested discovers convention-named tests through check.red_discovery (changed test files) instead of a repo-wide collect.
---

# PLAN — mark-tested-scope

One phase is enough: the change is one discovery call in one function and its error text.

- Phase 1 — scoped bind. scope: `spec_machine.mark_tested` / `_mark_tested_locked` discovery and refusal text; tests in `tests/unit/test_mark_tested_scope.py`. exit: `uv run pytest -q tests/unit/test_mark_tested_scope.py tests/unit/test_hm_cost_p4_binding.py`. risk: a caller that runs `--ac` after committing its tests now gets a refusal. rollback: revert the commit; the yaml format is unchanged.

## 🚧 Contract Boundaries

### Do not change
- src/harness_maker/check.py (`red_discovery` is the oracle for AC-002)
- tests/unit/test_hm_cost_p4_binding.py
- specs/SPEC-hm-cost-p4.golden.json

ADR-001: reuse `check.red_discovery` for the bind, so bind and RED share one scope. **Decided by:** agent
ADR-002: no repo-wide fallback when no changed test file matches; refuse and name `--test-id`. **Decided by:** agent
ADR-003: the yaml is loaded once before the lock for discovery; a load failure leaves discovery empty and the locked path reports it as today. **Decided by:** agent
