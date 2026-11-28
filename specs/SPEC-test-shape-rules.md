---
type: spec
task_slug: test-shape-rules
status: approved
created: 2026-11-28
tags: [execute, spec, review, golden, maintainability]
test_framework: pytest
interview_rounds: 1
summary: A golden table is one call's arguments to its return value; extend an existing parametrize instead of a parallel table; a rule about the change itself is a reviewed Constraint, not a test.
---

# SPEC — test-shape-rules

## Intent

After SPEC-behaviour-named-tests (PR #94), the full tier 1+2 rerun still lost maintainability 9-15 to
plain + tests (36 pairs, Opus 5.5, position-swapped, evidence judge). The evidence clustered 11 of
the 15 losses into three test-side causes. A counterfactual on each, with hm's code unchanged and
only hm's test text edited, judged against the same plain change, confirmed all three:

- Golden table over something that is not one call → return value (6: t1-3, t4-2, t5-2, t10-3,
  t11-1, t11-2). These include argv → `{"rc", "stdout"}` dicts, call scripts and one-row tables. t11-1, with its one-row
  CLI table replaced by two plain asserts, went from maintainability B to **A** and overall B to **A**.
- Parallel table beside an existing parametrize (3: t7 ×3). t7-2, with its rows added to the
  existing `test_format` / `test_valid` lists, went from B to **A** on maintainability and overall.
- A test that polices the change itself (2: t10-1 repo secret scan, t11-3 `git diff` file
  check). Deleting only that test moved t10-1 from B to split and t11-3 from B to tie on
  maintainability; overall went from B to **A** and scope from B to tie in both pairs.

The other 4 losses concern the model's own production code (t9 ×3, t12-2). No test text explains
them, so they are out of scope. Data: `/mnt/project-files/hm-blog-cost/data/cf-*.json`.

Where each cause comes from:
- `/hm:spec` says a behaviour-unchanged AC "is parametric". Nothing in it says a golden row is a
  call's return value, so a CLI or step-script AC also becomes a table.
- `/hm:execute` always writes a new named block, so an existing list is never extended.
- Nothing says that a rule about the diff (files touched, no secret) is not code behaviour, so
  the model writes it as a mechanical AC and a test.

## Outcomes

- Golden tables written from now on map one function's arguments to its return value, with two
  or more rows. Everything else becomes a mechanical AC with a plain assert.
- When the module's test already parametrizes the same call, the AC's rows go into that list and
  that test is bound to the AC.
- A rule about the change itself is a SPEC Constraint that the reviewer checks, with no test.

## In-Scope Scenarios

- S1 (normal): Given parametric AC-001 with 2 rows, when `export-golden --inline --slug s --ac
  AC-001` runs (no `--write`), then stdout is exactly those rows as `    (5430, 1, "2h"),` lines
  and nothing for other ACs.
- S2 (failure): Given `--ac AC-009` that is not a parametric AC, then exit 1 and stdout empty.
- S3 (normal): Given a bound existing test whose inline list gains the printed rows, when `hm
  check` runs, then no drift (already covered by SPEC-behaviour-named-tests AC-004, "extended").
- S4 (normal): Given the rendered spec/execute/reviewer text, then it carries the three rules.

## Non-Goals

- The 4 code-side losses (t9, t12-2).
- A finalize check that rejects one-row tables or tree-policing ACs. These are text rules first;
  measure before adding a gate.
- Changing the judge or the bench.
- Adding a secret scan to `hm check`.

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| stage size | after trims: spec +97, execute +43 chars, re-pinned with the reason (two older pinned rules kept verbatim); code-reviewer ≤ 3000 chars |
| compat | `--ac/--name --write` and the legacy `AC_NNN_ROWS` write keep today's behaviour |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: export-golden prints one AC's rows for pasting into an existing list
`export-golden --inline --slug <slug> --ac AC-NNN` with no `--write` and no `--name` prints only
that AC's rows, one `    <py_literal(row)>,` line each (flat when the keys allow, else pairs), and
exits 0. An AC that is not parametric exits 1 with empty stdout. `--name` without `--write` still
exits 2.
- oracle_source: golden. Expected stdout fixed in the test.

### AC-002: execute extends an existing parametrize before writing a new block
The rendered `/hm:execute` (Claude and Codex) says a parametric AC whose call a test there already
parametrizes adds the printed rows to that list and binds that test, and otherwise writes the
`--ac AC-NNN --name` block. It keeps every SPEC-behaviour-named-tests phrase.
- oracle_source: golden. Phrases fixed here before the template change.

### AC-003: spec keeps golden tables to call → return value and the diff rules out of ACs
The rendered `/hm:spec` says a golden row maps arguments to the return value. It also says printed
output, exit codes, call sequences and a lone case are mechanical ACs, and that a rule about the
change itself (files touched, no secret committed) is a Constraint the review checks, not an AC.
The behaviour-unchanged rule no longer says the AC "is parametric".
- oracle_source: golden. Phrases fixed here before the template change.

### AC-004: the reviewer checks SPEC Constraints
The rendered code-reviewer lists the SPEC's Constraints among what it checks.
- oracle_source: golden. Phrase fixed here before the template change.

## Verification

| scenario | mode | AC |
|---|---|---|
| S1 | unit | AC-001 |
| S2 | unit | AC-001 |
| S3 | unit | existing test (test_behaviour_named_tests extended-list drift) |
| S4 | unit | AC-002, AC-003, AC-004 |
| bench | manual | t7 + t11 ×1 with the evidence judge first, then 4 tasks, then tier 1+2 on a card |

## Open Questions

none

## Refinement Decisions

- **Print, then paste, for an existing list** (agent-decided): an AST rewrite of someone else's
  decorator is fragile, while a mistyped row is still caught by the parametrize-based drift check.
  Undo: one flag path.
- **Text rules, no gate** (agent-decided): the counterfactuals show the shape that wins, but
  whether the model follows the text has to be measured. Undo: template text.
- **Constraint → reviewer** (agent-decided): plain + tests passes the bench's secret and scope
  traps without meta-tests. The reviewer already reads the SPEC. Risk: a secret slip that only a
  meta-test would have caught. The bench's trap columns will show it.
