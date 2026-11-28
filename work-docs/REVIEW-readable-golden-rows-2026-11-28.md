---
type: review
task_slug: readable-golden-rows
created: 2026-11-28
spec: "[[SPEC-readable-golden-rows]]"
---

# REVIEW — readable-golden-rows

One code-reviewer pass over 36210192..80e5aa58 (two WIP commits); fixes in the third.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P1 | src/harness_maker/spec_machine.py:_run_export_golden | With tests added to a module's existing file, `--write` could overwrite another SPEC's same-numbered `AC_NNN_ROWS` (the name has no slug), and `hm check --slug` of this SPEC alone would not notice. | accepted | fixed: `_rows_owner` refuses (exit 1) when another SPEC's same AC id is bound to the target file; test `test_ac_002_write_refuses_another_specs_rows` |
| F2 | P2 | src/harness_maker/spec_machine.py:write_inline_rows | Re-running `--write` on a 0.67.0 pair block flattened it, breaking a test that unpacks dicts (e.g. tests/unit/test_intent_lean.py). | accepted | fixed: a block without a column header is rewritten in pair form (`flat=False`); AC-002 test updated |
| F3 | P2 | src/harness_maker/check.py:_inline_golden_drift | Flat rows are positional; a renamed or reordered SPEC key with the same values gave no drift. | accepted | fixed: flat rows also need today's `# (cols, expected)` header above the constant; test `test_ac_003_flat_rows_need_todays_column_header`. Residual: after a key reorder, `--write` rewrites rows and header but not the test's parametrize names (recorded, not fixed) |
| F4 | P2 | tests/unit/test_inline_golden_rows.py:27 | SPEC-inline-golden-rows AC-001's approved predicate still asserted pairs while its test was edited to flat. | accepted | fixed: that AC is retired `--by readable-golden-rows`; its test moved to `test_ac_001_export_inline_cli_prints_flat_rows_and_writes_no_json`; the old file is restored otherwise |
| F5 | P2 | src/harness_maker/templates/stages/execute.md.j2:7 | The `--no-tdd` notice text, part of SPEC-hm-overhaul-p1's CLI contract, was shortened. | accepted | fixed: restored verbatim; other trims pay for it |
| F6 | P3 | src/harness_maker/spec_machine.py:write_inline_rows | The header alternative `^# \(...\)` could swallow a user comment such as `# (see issue 42)`. | accepted | fixed: matches only `# (input, expected)` or `# (<identifier>, …, expected)`; covered in the AC-002 test |
| F7 | P3 | specs/SPEC-readable-golden-rows.machine.yaml:19,46 | The AC-001/AC-002 `executable_predicate`s still pass the removed `spec_name` argument. | rejected | predicates are not executed (`check.py` never evaluates them; tests bind); editing them would void the DRI's approval for a doc-only drift. Noted in the SPEC |
| F8 | P3 | execute.md.j2, spec.md.j2 | Budget-driven trims are not listed in the PLAN. | accepted | fixed: PLAN ADR-003 lists them |
