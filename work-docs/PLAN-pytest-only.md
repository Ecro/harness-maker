---
type: plan
task_slug: pytest-only
status: complete
created: 2026-11-10
spec: "[[SPEC-pytest-only]]"
summary: no_runner_reason names the pytest-only limit on a root with no Python test setup; the README states the limit.
---

# PLAN — pytest-only

- Phase 1 — scope: `check.py` `no_runner_reason` gains a non-Python branch (`_PY_MARKERS`); exit: `uv run pytest -q tests/unit/test_pytest_only.py`; risk: a Python project laid out without any root marker gets the pytest-only text instead of "no pytest runner"; rollback: revert `check.py`.
- Phase 2 — scope: README requirements row and stack-detection bullet state that the RED and AC gates run pytest only; exit: `grep -n "pytest only" README.md`; risk: none; rollback: revert README.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/spec_machine.py`
- `src/harness_maker/templates/`

ADR-001: the non-Python test reads root files only (no profiler call), because `hm check` must stay cheap and the profiler is not imported there. **Decided by:** agent
