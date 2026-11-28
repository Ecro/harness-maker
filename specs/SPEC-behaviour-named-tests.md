---
type: spec
task_slug: behaviour-named-tests
status: approved
created: 2026-11-28
tags: [execute, spec, check, golden, maintainability]
test_framework: pytest
interview_rounds: 1
summary: Tests are named for behaviour, not AC ids; the AC link moves into the SPEC (`bind`), rows print in repo quotes, and a golden table covers one call shape.
---

# SPEC — behaviour-named-tests

## Intent

After SPEC-readable-golden-rows (PR #93), hm still lost maintainability 7-27 to plain + tests
(Opus 5.5, position-swapped, 36 tier 1 + 2 pairs). The judge was made to cite its evidence (side,
file, quoted lines, decisive) and the causes were then checked by counterfactual diffs: hm's code
unchanged, only hm's test text edited, judged against the same plain change
(`/mnt/project-files/hm-blog-cost/CAUSES-maintainability-2026-11-28.md`).

- Code is not the cause: hm code + plain tests ties plain (t1-3, t9-1).
- Requirement-id names (`AC_001_ROWS`, `test_ac_001_*`, ids `AC-001-i`) are the decisive evidence
  in 17 of 27 losses. Renaming them by behaviour plus repo-style double quotes (rows are written
  with `repr`, single quotes) turned t1-3 from a loss to a tie and t3-1 to an hm win.
- A golden table that spans two functions forces string dispatch in the test
  (`normalize(arg) if fn == "normalize" else total(arg)`, 6 losses). One table per function turned
  t12-1 from a loss to a split.
- Moving the rows from a module constant into the decorator changed nothing (t1-3, t3-1).

Names carry the AC link today (`ac_tests_for`, RED discovery), so the link has to move first:
execute records each AC's tests in the SPEC before RED, and `hm check` finds the rows through the
bound test's own `parametrize` instead of a constant name.

## Outcomes

- A test file written by `/hm:execute` holds no AC id: test names, case ids and row constants are
  named for the behaviour.
- `hm check --red`, `mark-tested` and `hm check` still know each AC's tests and still catch a
  changed golden row.
- Rows written by `export-golden` read like the repo's own literals (double quotes, no comment).
- Tests written by 0.67.x (convention names, `AC_NNN_ROWS`) keep binding and checking unchanged.

## In-Scope Scenarios

- S1 (normal): Given Phase A tests named `test_max_units`, when `bind --test-id
  AC-001=tests/test_format.py::test_max_units` runs, then the AC's `test_ids` hold it, it stays
  pending, and `hm check --red` runs that test for AC-001.
- S2 (failure): Given a `--test-id` whose file or function does not exist, then `bind` exits 1
  and the yaml is byte-identical.
- S3 (normal): Given `export-golden --inline --write tests/test_format.py --ac AC-001 --name
  MAX_UNITS_CASES`, then the file gains `MAX_UNITS_CASES = [(5430, 1, "2h"), ...]` and nothing for
  other ACs.
- S4 (normal): Given a bound test whose `parametrize` takes the rows as a constant, an inline list
  or an existing list extended with them, when `hm check` runs, then there is no drift.
- S5 (failure): Given one row value edited in that list, then the AC drifts.
- S6 (compat): Given a 0.67.x test named `test_ac_001_*` over `AC_001_ROWS`, then binding and
  drift behave as before.

## Non-Goals

- Moving rows into the decorator (no measured effect); either place passes the check.
- Changing the machine.yaml schema or approval hash: `test_ids` is already a tooling field.
- Copied existing cases and rows in the wrong module's file (causes 4-5): evidence only, no
  counterfactual yet. `--ac` writes one AC per file, which removes the mechanism of cause 5.
- Changing the judge prompt or `pairwise_judge.py`.

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| drift rule | every SPEC row (flat or pair projection) is an element of the values one bound `parametrize` resolves to; extra rows allowed |
| resolvable values | a list/tuple literal, a module constant holding one, or a comprehension over `NAME` / `enumerate(NAME)` |
| compat | `AC_NNN_ROWS` blocks and `test_ac_NNN` names keep today's behaviour |
| stage size | execute and spec within every size ratchet (trims, no budget raise) |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: bind records an AC's tests before RED
`hm spec_machine bind --slug <slug> --test-id AC-NNN=<node id> ...` adds the ids to each AC's
`test_ids` without running pytest, leaves `pending_test` true and the approval valid, and refuses
(exit 1, yaml byte-identical) an unknown AC or an id whose file or test function is not in the
tree. `hm check --red` then runs the bound tests.
- oracle_source: golden. Fixture SPEC and test files fixed in the test.

### AC-002: export-golden writes one AC's rows under a chosen name
`export-golden --inline --write <file> --ac AC-NNN --name NAME` writes only that AC's rows as
`NAME = [...]` (flat when the keys allow, else pairs) with no comment line and double-quoted
strings, replaces an existing `NAME` block holding the same rows in place, and refuses (exit 1,
file untouched) a `NAME` that holds other rows. `--name` without `--ac`, or a name that is not an
identifier, exits 2.
- oracle_source: golden. Expected file bytes fixed in the test.

### AC-003: printed rows read back exactly
For seeded random rows of str (quotes, backslashes, newlines, non-ASCII), int, float, bool, None,
list, tuple and dict, `ast.literal_eval` of the printed literal equals the value, and a string with
no `"` in it prints between `"`.
- oracle_source: property. `ast.literal_eval` is Python's reader, independent of the printer.

### AC-004: hm check finds rows through the bound test's parametrize
For a parametric AC whose bound test parametrizes over a constant, an inline list, or
`[pytest.param(*r, ...) for i, r in enumerate(NAME)]`, `_inline_golden_drift` reports no drift
when every SPEC row is among the values (extra rows allowed), names the AC when a row value
changes or a row is missing, and still returns None for a test that reads `load_golden_table`.
- oracle_source: golden. Fixture SPEC and test files fixed in the test.

### AC-005: execute names tests for behaviour and binds them
The rendered `/hm:execute` (Claude and Codex) has no `test_ac_NNN`, `AC-NNN-<i>` or `AC_NNN_ROWS`;
it says no AC id goes in a test name, case id or constant, gives the `--ac AC-NNN --name` write
and a `bind` call before RED; it still says never to copy the implementation and has no
`spec_machine validate`.
- oracle_source: golden. Phrases fixed here before the template change.

### AC-006: spec keeps a golden table to one call shape
The rendered `/hm:spec` says a golden table's inputs are one function's arguments, split rather
than add a column naming the function or a script of steps.
- oracle_source: golden. Phrase fixed here before the template change.

## Verification

| scenario | mode | AC |
|---|---|---|
| S1 | unit | AC-001 |
| S2 | unit | AC-001 |
| S3 | unit | AC-002, AC-003 |
| S4 | unit | AC-004 |
| S5 | unit | AC-004 |
| S6 | unit | existing tests (test_inline_golden_rows, test_readable_golden_rows) |
| bench | manual | 1-2 tasks first (t1, t12) + evidence judge, then tier 1+2 on a card |

## Open Questions

none

## Refinement Decisions

- **Link in the SPEC, not the test** (agent-decided): `test_ids` is already hash-excluded tooling
  state, so recording it before RED needs no schema change. A marker or comment with the AC id
  would leave the id in the test (the ids-as-comments ablation lost 7-27). Undo: template text.
- **Check reads the bound test's parametrize** (agent-decided), not a constant name: names are the
  model's now, and a decorator read also accepts an extended existing list. Undo: one function.
- **Constants stay allowed** (agent-decided): the move-into-decorator counterfactual showed no gain.
- **Retires** SPEC-hm-cost-p4 AC-004 (convention names, `AC-NNN-<i>`) and SPEC-inline-golden-rows
  AC-003 (`AC_NNN_ROWS` in execute); SPEC-hm-cost-p2 AC-003's pin on `AC_NNN_ROWS` follows the text.
