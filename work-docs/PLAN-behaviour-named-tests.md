---
type: plan
task_slug: behaviour-named-tests
status: complete
created: 2026-11-28
spec: "[[SPEC-behaviour-named-tests]]"
summary: Move the AC link out of test names into the SPEC (bind), write rows under a chosen name in repo quotes, find rows through the bound parametrize, one golden table per function.
---

# PLAN — behaviour-named-tests

One phase is enough: the CLI pieces, the check and the stage text change together and share one test file.

- Phase 1 — scope: spec_machine (bind, py_literal, write_named_rows, export-golden --ac/--name), check (_parametrized_values), execute/spec templates, pinned tests. exit: `uv run pytest tests/unit/test_behaviour_named_tests.py tests/unit/test_overhaul_p1_surface.py tests/unit/test_cli_bookkeeping.py -q`. risk: a test bound before RED whose file never collects. rollback: revert the commit; recorded test_ids stay valid under the old flow.

## 🚧 Contract Boundaries

### Do not change
- src/harness_maker/second_opinion_invoke.py
- specs/SPEC-readable-golden-rows.machine.yaml

ADR-001: `bind` writes `test_ids` before RED without collecting; mark-tested still collects after GREEN. **Decided by:** agent
ADR-002: drift reads the bound test's `parametrize` (literal, constant, comprehension over a constant); `AC_NNN_ROWS` keeps the old path first. **Decided by:** agent
ADR-003: the old `--inline` print path keeps `repr`; only the named write uses double quotes, so 0.67.x blocks and their tests stay byte-stable. **Decided by:** agent
ADR-004: stage budgets held by trims (spec: the "is circular" sentence, the `/hm:execute writes` sentence; execute: shorter Phase A wording). **Decided by:** agent
ADR-005: SPEC-cli-bookkeeping's `--ac AC-NNN` pin now names mark-tested only, since export-golden's one-AC write uses the same flag spelling. **Decided by:** agent
