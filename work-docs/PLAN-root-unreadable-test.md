---
type: plan
task_slug: root-unreadable-test
status: complete
created: 2026-11-10
spec: "[[SPEC-root-unreadable-test]]"
summary: Make the [unreadable] row of test_land_hold hold as root by failing that one read when the process can read a mode-000 file.
---

# PLAN — root-unreadable-test

One phase is enough: the change is one branch of one test.

- Phase 1 — scope: `tests/unit/test_land_hold.py` unreadable row; exit: `uv run pytest -q "tests/unit/test_land_hold.py::test_ac_011_the_subject_hash_refuses_an_oversized_subject"`; risk: the row stops testing a real permission failure for non-root users; rollback: revert the test file.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/spec_machine.py`

ADR-001: as root, patch `Path.read_bytes` for the one resolved path rather than skip the row. **Decided by:** agent
