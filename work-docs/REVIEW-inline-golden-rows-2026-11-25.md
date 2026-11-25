---
type: review
task_slug: inline-golden-rows
created: 2026-11-25
spec: "[[SPEC-inline-golden-rows]]"
plan: "[[PLAN-inline-golden-rows]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round: 12 findings (5 P2, 7 P3), no P0/P1. Eleven accepted and fixed, one rejected."
---

# REVIEW — inline-golden-rows

One code-reviewer round on the uncommitted diff. The reviewer probed `with_golden` on fixture
projects: the `repr` / `literal_eval` round trip is exact for floats (0.1, 1e300, -0.0), None,
bools, nested containers and quotes; superseded ACs are skipped. Python's `True == 1 == 1.0` can
hide a type swap, as on the JSON path. No `Do not change` path was crossed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | src/harness_maker/check.py `_literal_rows` | With test_ids in several files, only the first file holding the constant was compared. Fix: every defining file is compared; test added | accepted | SPEC AC-002 |
| F2 | P2 | src/harness_maker/check.py `with_golden` | With a golden JSON present the inline rows were never compared, so rewriting the JSON passed while pasted rows drifted. Fix: both are compared; test added | accepted | SPEC Intent (drift guarantee) |
| F3 | P2 | tests/unit/test_hm_cost_p2_templates.py:43 | `test_ac_003_red_without_harness_maker` still built a JSON-reading test. Fix: it now pastes an `AC_001_ROWS` literal | accepted | SPEC AC-003 |
| F4 | P2 | tests/unit/test_inline_golden_rows.py | The sibling rule and non-literal rows had no test. Fix: tests for a sibling AC without rows and for `pytest.param` / comprehension rows | accepted | SPEC AC-002 |
| F5 | P2 | src/harness_maker/templates/stages/execute.md.j2:45 | The prose did not say the constant is module level. Fix: "top level and unchanged" | accepted | SPEC AC-003 |
| F6 | P3 | src/harness_maker/check.py red discovery | `AC_\d+_ROWS` bound every unbound parametric AC to any file holding any rows constant. Fix: matches `inline_rows_name(ac.id)` per AC | accepted | binding precision |
| F7 | P3 | src/harness_maker/check.py absent hint | Read as "paste the command". Fix: "paste the output of" | accepted | wording |
| F8 | P3 | src/harness_maker/spec_machine.py `golden_inline_text` | The printed header comment was ~120 chars (E501 in projects that enable it). Fix: two lines | accepted | bench `ruff_new` |
| F9 | P3 | src/harness_maker/spec_machine.py `golden_export` | Inline mode inherits the JSON round-trip check, so an int dict key refuses both forms | rejected | SPEC Refinement Decisions (one rule for both forms; rare) |
| F10 | P3 | src/harness_maker/spec_machine.py:2524 | `export-golden` help named only the JSON. Fix: mentions `--inline` | accepted | CLI accuracy |
| F11 | P3 | tests/unit/test_inline_golden_rows.py | The JSON-verdict test used equal rows, so it showed nothing. Fix: replaced by the F2 test with differing inline rows | accepted | test strength |
| F12 | P3 | specs/SPEC-inline-golden-rows.md Verification | The regression row named test files in the AC column. Fix: names SPEC-hm-cost-p2's ACs | accepted | this SPEC's AC-004 |
