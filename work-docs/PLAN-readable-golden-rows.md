---
type: plan
task_slug: readable-golden-rows
status: complete
created: 2026-11-28
spec: "[[SPEC-readable-golden-rows]]"
summary: Flat, header-light inline golden rows (spec_machine + check) and two stage sentences (execute placement/unpack, spec raising/unchanged cases).
---

# PLAN — readable-golden-rows

- Phase 1 — rows and check. scope: `src/harness_maker/spec_machine.py` (`golden_inline_text`, `write_inline_rows`, new `inline_rows_projection`), `src/harness_maker/check.py` (`_inline_golden_drift`). exit: `uv run pytest tests/unit/test_readable_golden_rows.py tests/unit/test_inline_golden_rows.py tests/unit/test_cli_bookkeeping.py -q`. risk: a 0.67.0 block not matched, giving a second `AC_NNN_ROWS`. rollback: revert the two functions.
- Phase 2 — stage text. scope: `src/harness_maker/templates/stages/execute.md.j2`, `src/harness_maker/templates/stages/spec.md.j2`, snapshots. exit: `uv run pytest tests/unit/test_readable_golden_rows.py tests/unit/test_overhaul_p1_surface.py tests/unit/test_ask_less.py -q`. risk: stage char budgets. rollback: revert the two sentences.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/spec_machine.py::golden_export` (the projection the JSON and the check share)
- `scripts/` (the bench and judge stay the fixed instrument)
- `tests/unit/test_overhaul_p1_surface.py` budgets

ADR-001: Flat rows only when every row's input is a dict with the same identifier keys in the same order; otherwise the 0.67.0 pair form. **Decided by:** agent
ADR-002: SPEC-inline-golden-rows AC-001 is retired `--by readable-golden-rows`; its test (flat rows, no JSON written) moves to this SPEC's test file. **Decided by:** agent (review F4)
ADR-003: Stage size is kept with no budget raise by trimming wording elsewhere: execute drops "Restate `Do not change` once", the RED exit-1 example list, and shortens the chain, flaky-test, RED-summary and first-party-import sentences; spec shortens "writes and binds each non-judgment AC's test", "(the check; it writes nothing)" and "(from the last `finalize`)". Every phrase another SPEC's test pins is kept. **Decided by:** agent (review F8)
ADR-004: Existing pair blocks stay pairs on rewrite; only new blocks and column-header blocks are flat. `--write` refuses a file whose same-numbered rows belong to another SPEC. Flat rows drift unless today's column header sits above them. **Decided by:** agent (review F1-F3)
