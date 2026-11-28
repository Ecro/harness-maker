---
type: spec
task_slug: readable-golden-rows
status: approved
created: 2026-11-28
tags: [execute, spec, check, golden, maintainability]
test_framework: pytest
interview_rounds: 1
summary: Inline golden rows read like ordinary pytest parameters (column header, flat tuples, no tool notes), and execute/spec stop the test shapes the pairwise judge marks as hm residue.
---

# SPEC — readable-golden-rows

## Intent

On 0.67.0 (main 29fa9f84), hm lost to plain + "write tests" in the Opus 5.5 position-swapped
pairwise judge on maintainability 3-29 and scope discipline 0-30 (36 pairs, tier 1 + 2,
`/mnt/project-files/hm-blog-cost/data/pj-all-067-ptests.json`). Production code was the same size
(25.7 vs 24.2 changed lines); only the tests differ (96 vs 40 lines). The losing reasons, by
pair:

1. The inline rows' header `# Do not edit; hm check compares them with the SPEC` (35 of 36 pairs).
   Deleting those two comment lines from the same trees moved scope to 1-14 and maintainability
   only to 5-27 (`pj-all-067a1`); a one-line pointer to the SPEC instead gave 0-23 (`067a2`).
2. Adapter code around `(input_dict, expected)` rows: `f(**kwargs)`, a `"ValueError"` string as
   the expected value, `getattr(builtins, …)`, `eval(row["call"])` (26 of the 27 maintainability
   losses after (1) was removed).
3. A new test file although the module already has one (20/36 hm runs vs 2/36 plain + tests,
   counted only where no new module was added; 15 of 27 losses).
4. Behaviour-unchanged ACs that copy cases the existing tests already assert (5-9 losses).

hm keeps what it is for: rows fixed at spec time and compared by `hm check`, tests named by AC,
the full suite gate. Only the shape of what lands in the test file changes.

## Outcomes

- `export-golden --inline` writes rows a reader can parametrize directly: a column header comment
  and flat tuples when every row's input has the same keys, with no tool or "do not edit" note.
- `hm check` treats the flat rows exactly like the pair rows: equal passes, any change drifts.
- Rows written by 0.67.0 (old header, pair form) are still replaced in place and still compared.
- The rendered execute stage asks for tests in the module's existing test file, unpacked rows and
  plain calls; the rendered spec stage keeps raising cases and already-tested behaviour out of
  golden rows.

## In-Scope Scenarios

- S1 (normal): Given an AC whose rows all take `{seconds, max_units}`, when `export-golden
  --inline` runs, then it prints `# (seconds, max_units, expected)` and rows like `(5430, 2, '2h')`.
- S2 (edge): Given rows whose input keys differ, or an input that is not a dict, or a key that is
  not an identifier or is `expected`, then it keeps the `(input, expected)` pair form under
  `# (input, expected)`.
- S3 (compat): Given a test file holding a 0.67.0 block (`golden rows from …` + `Do not edit`),
  when `--write` runs, then that block is replaced in place and no second block appears.
- S4 (failure): Given a flat row edited in the test, when `hm check` runs, then the AC drifts.
- S5 (normal): Given the rendered execute and spec stages, then they carry the placement, unpack
  and raising-case rules.

## Non-Goals

- Changing the machine.yaml `golden_table` schema or the JSON golden mode.
- Rewriting this repository's own existing inline-row tests (they stay valid in pair form).
- Changing the judge (`pairwise_judge.py`). Its blind spot (SPEC files are not in the judged diff,
  so a pointer to one reads as "a missing doc") is recorded, not fixed: removing the pointer makes
  it moot, and the instrument stays fixed so 0.67.0 and this change compare on one scale.
- AC ids in test names (`test_ac_NNN_*`): binding depends on them and only 1 of 27 reasons named them.

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| flat form | only when every row's input is a dict with the same keys in the same order, each an identifier other than `expected` |
| drift rule | rows equal the pair projection or the flat projection of `golden_export`, order-sensitive |
| stage size | execute and spec within every size ratchet (no budget raise; trims in PLAN ADR-003) |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: inline rows print flat under a column header
`spec_machine.golden_inline_text` prints, for an AC whose rows all share identifier keys,
`# (k1, …, expected)` then `AC_NNN_ROWS = [(v1, …, expected), …]`; otherwise `# (input, expected)`
and pair rows. The output never contains `Do not edit`, `hm check` or the SPEC file name, and
`ast.literal_eval` of the list gives the flat (or pair) projection.
- oracle_source: golden. Expected text fixed in the test from hand-written rows.

### AC-002: --write replaces old and new blocks in place
`write_inline_rows` on a file holding a 0.67.0 block (two old header lines) or a new-header block
replaces it where it is, leaves every other byte, and adds no second `AC_NNN_ROWS`. A block with no
column header stays in pair form (its test unpacks dicts); a user comment above a block survives;
`--write` refuses (exit 1) a file whose same-numbered rows another SPEC binds.
- oracle_source: golden. Fixture files fixed in the test.

### AC-003: hm check accepts flat rows and still catches drift
`check._inline_golden_drift` returns no drift for flat rows equal to the SPEC and for pair rows
equal to the SPEC, and names the AC when one flat row value changes, a row is missing, or the
column header above flat rows no longer names the SPEC's keys.
- oracle_source: golden. Fixture SPEC and test rows fixed in the test.

### AC-004: execute asks for placement, unpacked rows and plain calls
The rendered `/hm:execute` Phase A says to add each test to the existing test file of the module it
exercises (a new file only for a new module) and to unpack the row columns as parametrize names and
call the code plainly, with no `eval`, `getattr` or string stand-ins.
- oracle_source: golden. Phrases fixed here before the template change.

### AC-005: spec keeps raising cases and already-tested behaviour out of golden rows
The rendered `/hm:spec` says a case that must raise is a mechanical AC (`pytest.raises`), not a
golden row, and that a behaviour-unchanged AC covers only behaviour no existing test asserts.
- oracle_source: golden. Phrases fixed here before the template change.

## Verification

| scenario | mode | AC |
|---|---|---|
| S1 | unit | AC-001 |
| S2 | unit | AC-001 |
| S3 | unit | AC-002 |
| S4 | unit | AC-003 |
| S5 | unit | AC-004, AC-005 |
| bench | manual | tier 1+2 hm rerun + pairwise vs plain + tests (result recorded in the PR) |

## Open Questions

none

## Refinement Decisions

- **No header pointer to the SPEC** (agent-decided). The a2 ablation (pointer kept) was worse on
  scope than a1 (nothing) and `hm check` already names the SPEC when rows drift. Undo: one line.
- **Column header instead of an `AC_NNN_ARGS` constant** (agent-decided): no new name for the
  check to bind; the test writes its own parametrize names. Undo: minutes.
- **Raising cases out of golden rows** (agent-decided): the JSON row cannot hold an exception, so
  every model invented a stand-in. A mechanical AC keeps the oracle. Undo: one sentence.
- **Review fixes** (agent-decided, REVIEW F1-F6): pair blocks stay pairs, cross-SPEC overwrite refused, column header checked, SPEC-inline-golden-rows AC-001 retired by this SPEC. The AC-001/AC-002 predicates still show the removed `spec_name` argument; predicates are not executed, so they were left to keep the approval (F7).
- **Behaviour-unchanged AC only for behaviour no test asserts** (agent-decided): the full suite gate
  already guards the rest; copying it was judged duplication. Risk: test_protection may drop a
  little; the rerun measures it. Undo: one sentence.
