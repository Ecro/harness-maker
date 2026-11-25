---
type: spec
task_slug: inline-golden-rows
status: approved
created: 2026-11-25
tags: [design, execute, spec, check, golden, maintainability]
test_framework: pytest
interview_rounds: 1
summary: Parametric AC tests carry their golden rows inline as an `AC_NNN_ROWS` literal that `hm check` compares with the SPEC, instead of reading SPEC-<slug>.golden.json; the SPEC Verification table names ACs, never test names.
---

# SPEC — inline-golden-rows

## Intent

The 2026-11-25 cost/value bench (`/mnt/project-files/hm-blog-cost/`, section 5) found two ways hm's
own artifacts make the code it ships harder to maintain:

1. **Golden JSON indirection.** `/hm:execute` tells the model to parametrize a parametric AC's
   test over rows read with `json` from `specs/SPEC-<slug>.golden.json`. A reader of the test sees
   neither inputs nor expectations. In the Opus 5.5 position-swapped pairwise judgement hm lost to
   plain + "write tests" on maintainability 4-29 (0-33 in the per-task rows), and the judge's
   reasons named this indirection again and again. The file also drove the mid-file
   `import json` / `from pathlib import Path` blocks (SPEC-bench-wrapup-defects defect 3).
2. **Verification table drift.** The spec stage writes `Verification (scenario, mode, test)`
   before any test exists; execute then names tests `test_ac_NNN_<short>`. The reviewer flagged
   the mismatch in 6 bench tasks, and 12 of 60 accepted findings were hm's own documents
   disagreeing with each other.

The JSON file exists for a reason worth keeping: rows are fixed at spec time and `hm check` fails
when the test's oracle drifts from the SPEC ("never regenerate golden rows"). Inline rows keep that
guarantee if `hm check` compares them.

## Outcomes

- A parametric AC's test shows its rows: an `AC_NNN_ROWS = [(input, expected), …]` literal in the
  test file, printed by `hm spec_machine export-golden --inline` and pasted unchanged.
- `hm check` fails when those rows differ from the SPEC's `golden_table`, as it does for the JSON.
- A SPEC's Verification table maps scenarios to ACs; test names live only in `test_ids`.
- Projects with an existing golden JSON keep working unchanged.

## In-Scope Scenarios

- S1 (normal): Given a SPEC with a parametric AC, when execute runs `export-golden --inline`, then
  it prints one `AC_001_ROWS` literal whose rows equal the SPEC's (input, expected) pairs and writes
  no file.
- S2 (normal): Given the test file holds those rows, when `hm check` runs, then `ac.golden` is
  `inline` and the section passes.
- S3 (failure): Given a row edited in the test (or missing), when `hm check` runs, then the AC
  section fails with `golden_drift.acs` naming the AC and a fix that names `--inline`.
- S4 (compat): Given `SPEC-<slug>.golden.json` exists, when `hm check` runs, then the JSON verdict
  applies as before, and any inline rows are compared too; given neither JSON nor inline rows,
  `golden: absent` stays a hint, not a failure.
- S5 (normal): Given the spec stage, when it writes Verification, then the column names ACs.

## Non-Goals

- Removing `export-golden`'s JSON mode, `load_golden_table`, or the wrapup JSON glob. Old SPECs and
  tests still read them.
- Rewriting this repository's own golden-JSON tests.
- A CLI that renders the Verification table. Naming ACs removes the drift at its source, and
  `test_ids` already binds the tests.

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| row format | a top-level `AC_NNN_ROWS` list of `(input, expected)` tuples, readable by `ast.literal_eval` |
| drift rule | order-sensitive equality with `golden_export` (the same projection the JSON used) |
| stage size | no net growth in execute or spec beyond the measured change |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: export-golden --inline prints literal rows and writes no file
`hm spec_machine export-golden --inline --yaml <Y>` prints, per live parametric AC, an
`AC_NNN_ROWS = [...]` assignment whose `ast.literal_eval` value is the list of
`(input, expected)` pairs of its `golden_table`, and writes no `SPEC-<slug>.golden.json`.
- oracle_source: golden. Rows fixed in the test fixture; `ast.literal_eval` is Python's own reader.

### AC-002: hm check compares inline rows with the SPEC
With no golden JSON and a bound test file holding `AC_001_ROWS`: equal rows give
`golden: inline` and a passing section; a changed row or a missing row gives
`golden_drift.acs == ["AC-001"]`, a failing section, exit 1 and a fix naming `--inline`; so do
rows that are not a literal, a second bound file whose copy differs, and a sibling AC whose test
holds no rows while another AC's does. A test file with no rows anywhere keeps `golden: absent`
and passes. A golden JSON, when present, keeps the JSON verdict (`present`) and inline rows that
differ still drift.
- oracle_source: golden. Fixture rows fixed in the test, independent of the comparison code.

### AC-003: execute pastes inline rows
The rendered `/hm:execute` tells a parametric AC's test to paste the `AC_NNN_ROWS` list printed by
`export-golden --inline` and no longer names `golden.json`.
- oracle_source: golden. Phrase fixed here before the template change.

### AC-004: the spec Verification table names ACs
The rendered `/hm:spec` describes Verification as `(scenario, mode, AC)`, not
`(scenario, mode, test)`; test names live only in `test_ids`.
- oracle_source: golden. Phrase fixed here before the template change.

## Verification

| scenario | mode | AC |
|---|---|---|
| S1 | unit (subprocess) | AC-001 |
| S2, S3, S4 | unit (`check.run` on a fixture project) | AC-002 |
| S5 | render | AC-004 |
| execute prose | render | AC-003 |
| regression | unit | SPEC-hm-cost-p2 AC-002 and AC-003 (JSON path unchanged) |

## Open Questions

none

## Refinement Decisions

- Approval (DRI, 2026-11-25): option "인라인 + hm check가 SPEC과 대조" on the decision card in
  thread "벤치에서 찾은 hm 보완점 고치기". Design change: PR only, the DRI merges.
- Default (agent): the Verification fix (coordinator's suggestion was a CLI that generates the
  table) is a column change instead. A generated table would still be a second copy of
  `test_ids`; naming ACs leaves one copy. Undo: one template phrase.
- Default (agent): a bound test file with no `AC_NNN_ROWS` while a sibling AC has them is drift;
  with none anywhere it stays the old `absent` hint, so pre-existing projects do not start failing.
- Default (agent): SPEC-hm-cost-p2's `test_ac_003_execute_reads_golden_json` keeps its name (its
  `test_ids` stay bound) and now asserts the inline wording.
- Default (agent): inline export keeps `golden_export`'s JSON round-trip check, so a value JSON
  cannot hold (an int dict key) still refuses both forms. Rare, and one rule for both is simpler.
- Default (agent): no intent picked; spec-validator skipped (4 live ACs; `validator: skip`).
