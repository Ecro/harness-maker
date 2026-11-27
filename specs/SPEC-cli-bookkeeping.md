---
type: spec
task_slug: cli-bookkeeping
status: approved
created: 2026-11-27
tags: [cost, spec, execute, wrapup, spec_machine, cli]
test_framework: pytest
interview_rounds: 1
intent: HM-LIGHT-LANE
summary: The CLI does the SPEC bookkeeping the model now runs by hand (golden rows copied into tests, per-AC mark-tested flags, check/approve/status edits, the land manifest), so each stage makes fewer calls and writes fewer tokens with the same gates and file formats.
---

# SPEC — cli-bookkeeping

## Intent

The 2026-11-27 turn-level split of the blog bench (`/mnt/project-files/hm-turn-cost/REPORT-turn-cost-2026-11-27.md`)
found that hm's cost and time come mostly from output tokens and call count, not from instruction
length: main-session output 13.5k vs plain 2.2k tokens, 22.9 vs 3.7 calls, and the source code
written is the same size (1,059 vs 1,024 tokens). About 80% of hm's output is the model running
hm's own procedure. The largest piece is SPEC bookkeeping: 8.5 `spec_machine` calls per run, `sed`
edits of status fields, and long flag lists, about 10% of cost and 15% of wall time, with no
measured effect on any outcome.

The DRI chose (2026-11-27 card): move that bookkeeping from the model into the CLI. The rule the
DRI set for hm: keep only what the model does not do and will not do, and put it in lightly, in
code rather than in procedure the model executes.

## Outcomes

- The model never copies golden rows into a test file, never lists every AC to `mark-tested`,
  never edits a SPEC `status:` field to match an approval, and never types the land manifest.
- Every gate stays: `spec_machine check --all`, the approval stamp and content hash, RED,
  `hm check`, the review record gate, the land hold. File formats stay.
- On tier 1 the new hm arm costs less and finishes sooner than hm on main, with the same hidden
  test result.

## In-Scope Scenarios

- S1 (normal): execute Phase A runs `hm spec_machine export-golden --slug <slug> --inline --write
  tests/test_x.py`; the file gains `AC_NNN_ROWS` blocks, and the model writes only the test
  function that parametrizes over them. `hm check` reports no inline drift.
- S2 (normal): the spec stage runs `hm spec_machine finalize --slug <slug>` (check) and, on
  approval, `finalize --slug <slug> --approve`; the yaml is stamped and SPEC.md says
  `status: approved` in one call.
- S3 (edge): `export-golden --write` on a file that already holds `AC_001_ROWS` replaces that block
  in place and leaves every other byte; a second run changes nothing.
- S4 (failure): `finalize --approve` on a SPEC whose check fails stamps nothing, leaves `status`
  alone and exits 1.

## Non-Goals

- No change to the machine.yaml schema, the approval hash, golden JSON, or which gates run.
- No removal of REVIEW, PLAN, the reviewer, memory or intent steps (REVIEW is read by
  `hm check --require-review`, execute Resume and `review_effect`).
- No change to stage-end summaries or other prose beyond the steps replaced here.
- Old commands and flags keep working; nothing is removed from the CLI.

## Constraints

| Constraint | Source |
|---|---|
| pytest; ruff, ruff format, mypy --strict green | CLAUDE.md |
| Atomic writes (`io_utils.atomic_write`), no `shell=True`, timeouts on subprocesses | implementation-patterns.md |
| Claude and Codex renders change together (one template) | CLAUDE.md Targets |
| Rendered stage char budgets do not grow | `test_stage_budgets` / overhaul AC-004 |
| Boundary suite run locally before the PR | CLAUDE.md release section |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | Add `spec_machine finalize`, `--slug` and `--write` to `export-golden`, `--slug` to `mark-tested` with all testable ACs as the default when no `--ac` is given, and a default manifest to `wrapup_land` when no `--required`/`--optional` is given. Additive only. | public API/CLI contract | Rendered harnesses in user projects will call these; once shipped they cannot be renamed without breaking those renders. |

## Acceptance Criteria

### AC-001: export-golden --write puts the rows in the test file
`export-golden --slug S --inline --write F` creates F with each parametric AC's `AC_NNN_ROWS`
block when F is absent, replaces an existing same-name block in place (other bytes unchanged),
and a second run leaves F byte-identical; `hm check`'s inline golden drift is then empty.

### AC-002: mark-tested binds every testable AC by default
With `--slug S` and no `--ac`, every testable AC (not judgment, not superseded) that has a
convention-named test in the task's changed test files is marked; with `--ac` the behaviour is
unchanged.

### AC-003: finalize without a flag is the check
`finalize --slug S` prints the `check --all` JSON keys plus `approval` and `status`, exits with
check's exit code, and writes nothing.

### AC-004: finalize --approve stamps and sets status in one call
On a passing check, `--approve` stamps the yaml (approval state `approved`) and sets SPEC.md
frontmatter `status: approved`; `--exempt` does the same with state `exempt` and is refused when
`irreversible_decisions` is not empty; on a failing check neither stamps nor edits, exit 1.

### AC-005: wrapup_land has a default manifest
With no `--required`/`--optional`, `wrapup_land` lands the manifest the wrapup template passes
today for that slug (PLAN required; memory, REVIEW glob, RESEARCH, SPEC md, golden JSON,
machine.yaml optional); explicit flags replace it.

### AC-006: the stages call the CLI instead of doing the bookkeeping
In every rendered spec/execute/wrapup (Claude and Codex; Side and Production): spec uses
`finalize` for check, approve and exempt; execute uses `export-golden … --write` and
`mark-tested --slug` with no `--ac`; wrapup's land call has no `--required`/`--optional` and the
separate pre-land `approval-status` call is gone (the land's own hold prints the IRR ids). No
rendered stage grows in characters.

### AC-007: tier-1 bench shows fewer calls, less cost and less time
Tier 1, 3 runs per task, Sonnet 5.5, arms plain and hm from this branch plus hm from main in the
same window: hm-new mean cost ≤ 0.93 × hm-main, hm-new mean wall time ≤ 0.90 × hm-main,
hm-new hidden-test passes ≥ plain, and hm-new main-session Bash calls that run `hm` < hm-main.
The result, pass or miss, is recorded in this SPEC and in `docs/evals/RESULTS.md`.

## Verification

| scenario | mode | AC |
|---|---|---|
| S1 | unit | AC-001, AC-006 |
| S2 | unit | AC-003, AC-004, AC-006 |
| S3 | unit | AC-001 |
| S4 | unit | AC-004 |
| land default | unit | AC-005 |
| mark-tested default | unit | AC-002 |
| bench | integration (live, recorded rows) | AC-007 |

## Measured result

- verdict: missed
- 2026-11-27, tier 1, 15 runs per arm, Sonnet 5.5; rows in
  `tests/fixtures/cli_bookkeeping/bench_tier1.jsonl`, table in `docs/evals/cli-bookkeeping-2026-11-27.md`.
- hm-new vs hm-main: mean cost $0.439 vs $0.425 (+3%), mean wall 140.8 vs 135.1 s (+4%), hm
  Bash calls 12.0 vs 11.0, hidden-test passes 15/15 (plain 15/15). Bookkeeping subcommands fell
  7.6 -> 5.9 per run; review-and-fix loops set the mean. Medians: -7% cost, -2% wall.

## Open Questions

none

## Refinement Decisions

- **Keep machine.yaml as a model-written file** (agent). Moving its fields into SPEC.md would save
  only the duplicated titles (about 100–200 tokens); the rest of the yaml is the oracle (golden
  rows, predicates, oracle evidence) and has value. It would also change a file format. Undo: none
  needed.
- **Golden rows are written by the CLI, not pasted** (agent). Since #79 the model writes rows in the
  yaml, reads them back from `export-golden --inline`, and writes them again into the test: the
  same data three times in context. `--write` makes it once. Undo: template line.
- **`finalize` is a new subcommand, not new flags on `check`** (agent). `check` must stay read-only;
  a check that stamps would surprise other callers. Undo: one subcommand.
- **Drop the pre-land `approval-status` call** (agent). `wrapup_land` already runs `land_states`
  and exits with `hold: SPEC <slug> is <state>; irreversible: <ids>`; the template asks on that.
  Undo: template line.
- **Bar is relative to hm on main in the same window** (agent). The 6.77x baseline predates #79,
  so a same-window hm-main arm is the fair comparison. Thresholds come from the report's estimate
  (about −$0.03 to −$0.045 of $0.435, about −15 to −20 s of 142 s), set below it so noise does not
  decide. Undo: re-run.
- **Intent** HM-LIGHT-LANE: this task serves `hm_cost_ratio_small`.
- **spec-validator**: skipped by default (7 ACs ≤ 8).
