---
type: spec
task_slug: hm-cost-p2
status: approved
created: 2026-10-21
tags: [cost, eval, spec_machine, check, templates]
test_framework: pytest
interview_rounds: 2
intent: HM-LIGHT-LANE
summary: Cut hm-arm cost on small tasks by removing the RED-gate retry loop (golden rows via JSON, not a harness_maker import), folding approval into spec_machine check, compacting hm check output, exact IRR categories, edit-in-place docs and a short PLAN; pre-registered bar tier-1 ratio <= 12.5x.
---

# SPEC: hm cost, phase 2 (round trips, rewrites, PLAN size)

## 🎯 Intent
The tier-1 re-measure of 2026-10-21 at 473ac3f1 (0.65.1, claude-sonnet-5-5, 5 tasks x 3 runs) put hm at
14.31x plain by transcript price (12.66x CLI), against `hm_cost_ratio_small` target 5 and the phase-2
target 8. Both arms solved 15/15. Transcripts (archived at `~/hm-eval-archive/hm-eval-t1-2026-10-21.tgz`)
show cost is cache read 49%, output 32%, cache write 19%, over about 40 API calls per run against
plain's 4, with context growing from 28k tokens (spec) to 68k (wrapup).

Three causes are concrete and cheap to remove:
- **RED-gate retry loop.** `execute.md.j2` tells a parametric AC test to parametrize over
  `spec_machine.load_golden_table(...)`. A user project has no `harness_maker` package, so 13 of 15
  runs wrote a test that fails at collection; `hm check --red` reports it `error`, not RED. That is 31
  failed `hm check` calls, agents reading harness-maker source with `sed`, and stub rewrites. It also
  makes user tests depend on our package.
- **Avoidable re-checks.** 10 of 13 failed `spec_machine check` calls were `unknown category` for an
  irreversible decision, because the template lists the five categories as comma prose. Separate
  `approval-status` calls ran 28 times in 15 runs. `hm check` prints every section in full, and agents
  truncated it with `tail`/`cut` 56 times.
- **Whole-file rewrites.** The hm arm used Edit 0 times and Bash 483 times, rewriting the SPEC three
  times per run (4.8k, 3.0k, 2.9k chars) via heredoc. A single-phase task's PLAN was 3.9k chars, more
  than the code change (about 2.6k).

## 🌅 Outcomes
- A parametric AC's test reads its golden rows from `specs/SPEC-<slug>.golden.json` with the stdlib,
  and the RED gate passes on a user project that does not install `harness_maker`.
- `hm check` fails when that JSON and the machine.yaml golden tables disagree, so the SPEC stays the
  single source of truth.
- `/hm:spec` runs no separate `approval-status` call; `spec_machine check` carries the approval state.
- `hm check` prints passing sections as `ok` plus their warning keys only; `--full` prints the full output.
- The spec template lists the five irreversible categories verbatim.
- Stage templates tell the agent to change an already-written SPEC, machine.yaml, PLAN or REVIEW with
  Edit, and allow a short PLAN for a single-phase task.
- The tier-1 re-run on this harness is at or below 12.5x by transcript price, with hm's hidden-test
  pass rate at least plain's.

## 📋 In-Scope Scenarios

### S1: parametric AC on a project without harness_maker (AC-001, AC-002, AC-003)
**Given** a SPEC with a parametric AC and a project whose environment has no `harness_maker`
**When** execute runs `hm spec_machine export-golden` and writes the test against the JSON
**Then** the test fails for the missing implementation (RED), not at import, and `hm check --red` exits 0.

### S2: golden drift (AC-002)
**Given** a committed `SPEC-<slug>.golden.json`
**When** someone edits a row of the AC's `golden_table` in the machine.yaml and runs `hm check`
**Then** the `ac` section fails naming the AC and the command to re-export; with the JSON absent, the
section reports `golden: absent` with a `hint` naming `export-golden`, and does not fail on that
account (legacy tests via `load_golden_table` keep working). Wrapup lands the JSON with the SPEC.

### S3: spec stage without extra calls (AC-004, AC-005)
**Given** a SPEC with an irreversible decision
**When** `/hm:spec` writes it and runs `spec_machine check`
**Then** the category is one of the five verbatim values and the check output already holds
`approval` with the same state as `approval-status`.

### S4: compact gate output (AC-006)
**Given** a task where every `hm check` section passes but one
**When** `hm check --slug <slug>` runs
**Then** it prints one JSON line with the same `exit`, the failing section in full and every passing
section reduced to `ok` plus its keep-set keys; `--full` prints today's line plus `ac.golden`/`ac.hint`.

### S5: re-measure (AC-009)
**Given** the change merged into the checkout
**When** `scripts/bench_light_lane.py run --tier 1` runs with sonnet and the results are published
**Then** the tier-1 transcript ratio is <= 12.5 and hm's hidden-test pass rate is >= plain's.

## 🚫 Non-Goals
- Reintroducing lanes, folding stages, or reducing the reviewer or spec-validator (0.64.0 decisions).
- Removing `spec_machine.load_golden_table` (kept for existing tests).
- Fresh sessions per stage, or any change to Maker advance or the bench's DRI turn script.
- Reaching 8x or 5x in this task; the bar is 12.5x.
- Changing machine.yaml schema v3 or the approval hash.

## 🔒 Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest`; tests under `tests/unit/test_hm_cost_p2_*.py` | repo standard |
| JSON format | `{"<AC-id>": [{"input": ..., "expected": ...}, ...]}`, keys sorted, written atomically, only parametric ACs | stdlib-readable, deterministic |
| Absent JSON | not a failure; reported as `golden: absent` in the `ac` section | legacy SPECs predate the file (absent-case rule) |
| Output compaction | passing section -> `{"ok": true}`; `exit`, failing sections and key order unchanged | JSON consumers read by key |
| Surface | rendered stage surface grows by at most +263 claude / +281 codex chars, held as the PLAN's `surface_allowance` and recorded in `BASELINE-DELTA-hm-cost-p2.md`; execute/wrapup AC-004 budgets 7 250/3 850 | pinned wording elsewhere left no further cut; about 65 tokens per call (DRI, 2026-10-21) |
| PLAN short form | judged by the agent (no regex), one-line reason in the PLAN | LLM judgment principle |
| Bench | tier 1, `claude-sonnet-5-5`, 3 runs per cell, run on a clean committed tree, transcripts archived | comparable with 2026-10-21; a dirty sha cannot be pinned |
| Published rows | the re-run's rows replace `docs/evals/results.jsonl` (publish does not write it); `RESULTS.md` re-rendered from the same out dir; `test_overhaul_p1_ship_bar` stays green | appending mixes harness SHAs, which `summarize` refuses |
| Later evals | a later published eval retires AC-009 by marking it superseded, not by editing the fixture | the fixture pins this measurement |

## ⚠️ Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | New file `specs/SPEC-<slug>.golden.json` holding parametric golden rows, read by user tests | schema/file format/storage layout | user tests will depend on its path and shape |
| IRR-002 | `hm check` default output collapses passing sections to `{"ok": true}`; `--full` restores the full line | public API/CLI contract | scripts reading a passing section's detail must add `--full` |
| IRR-003 | New verb `hm spec_machine export-golden`; `spec_machine check` output gains an `approval` field | public API/CLI contract | rendered templates call the verb and read the field |

## ✅ Acceptance Criteria

### AC-001: export-golden writes the golden tables as JSON
`hm spec_machine export-golden --yaml specs/SPEC-<slug>.machine.yaml` writes
`specs/SPEC-<slug>.golden.json` holding, for each parametric AC that is not superseded, its
`golden_table` rows projected to `{"input", "expected"}`, keys sorted; a second run is byte-identical. A
SPEC with no such AC writes nothing and exits 0. A value JSON cannot hold (for example a YAML date)
exits nonzero naming the AC and row, and writes nothing.

### AC-002: hm check compares the JSON with the machine.yaml
In both `hm check` and `hm check --red`, the `ac` section fails (exit 1) naming each AC whose JSON rows
differ from its projected `golden_table`, or that is missing from the JSON, and names the re-export
command. Matching JSON adds nothing to the failure set. An absent JSON reports `golden: absent`, adds
nothing to the failure set, and, when the SPEC has a parametric AC, adds a `hint` naming the
`export-golden` command.

### AC-003: execute no longer sends tests to harness_maker
The rendered execute stage (Second Brain block on) tells a parametric AC test to read
`specs/SPEC-<slug>.golden.json` with the stdlib after running `export-golden`, and contains none of
`import harness_maker`, `from harness_maker` or `load_golden_table`. A test written that way against a
missing implementation is RED in an environment without `harness_maker`.

### AC-004: the stages list the irreversible categories verbatim
Every value of `spec_machine.IRREVERSIBLE_CATEGORIES` appears quoted, verbatim, in the rendered spec
stage and wherever the rendered execute stage lists the categories, and neither lists another category.

### AC-005: spec_machine check carries approval
`spec_machine check --all` output has an `approval` object whose `state`, `land` and `gate` equal those
`spec_machine approval-status` reports for the same SPEC. The rendered spec stage's Step 5 runs no
`approval-status`; it prints the state from the `approve` output when it stamps, else from a
`spec_machine check` run after the SPEC's last edit.

### AC-006: hm check compact output
A section passes when its exit code is 0 and `ok` is true. For the same tree, default `hm check` output
equals the `--full` output with each passing section reduced to `ok` plus the keys of a named keep-set
in `check.py` (at least `pending`, `notice`, `skipped`, `status`, `reason`, `waived`, `green_before`,
`golden`, `hint`), so a self-approved SPEC, a skipped CVE lookup and waived RED ACs stay visible.
`--full` output equals the 473ac3f1 output plus exactly the keys this SPEC adds (`ac.golden`,
`ac.hint`).

### AC-007: edit in place
The rendered spec and execute stages tell the agent that, once written, the SPEC, machine.yaml, PLAN
and REVIEW change in place (Edit for Claude Code, `apply_patch` for Codex), never by a whole-file
rewrite.

### AC-008: short PLAN for a single-phase task
The rendered execute stage allows, when the agent judges one phase enough and says why in one line, a
PLAN of frontmatter, one phase line, `Do not change` and only the ADRs actually decided. The PLAN
read-back still requires the four phase fields and a non-empty `Do not change`, and `wrapup_land`
accepts such a PLAN.

### AC-009: the tier-1 re-run meets the bar
The counted rows are those of `docs/evals/results.jsonl` whose `harness_sha` is listed in a committed
fixture `tests/fixtures/hm_cost_p2/harness_shas.json`, matched directly or through a squash alias
checked by tree hash (the `test_overhaul_p1_ship_bar` mechanism). Each listed SHA is a clean commit
(no `-dirty-`) reachable from HEAD and not from 473ac3f1. On those rows `bench.summarize` gives a
verdict other than `suspect` or `no_data`, its unrounded transcript ratio rounded to 3 decimals is <=
12.5, every tier-1 cell has 3 runs, every row's model is `claude-sonnet-5-5`, and hm's hidden-test pass
rate is >= plain's, counting a budget-capped or leak-suspect hm run as a failure. With no counted rows
the test fails, never skips.

### AC-010: wrapup lands the golden JSON
`derive_deliverable_globs` and the rendered wrapup's `--optional` list include
`specs/SPEC-<slug>.golden.json`, and `wrapup_land` stages it in a non-isolated fixture checkout.

## 🧪 Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit + integration | AC-001 golden fixture; AC-003 render check plus a subprocess pytest run with `harness_maker` hidden |
| S2 | unit | AC-002 golden table of match / drift / missing AC / absent |
| S3 | unit | AC-004 differential vs the Python tuple; AC-005 differential vs `approval-status` |
| S4 | unit | AC-006 differential: default vs `--full` vs a pre-change capture |
| S5 | integration (reads committed scorecard) | AC-009 |
| S1 (land) | integration | AC-010 non-isolated `wrapup_land` fixture |

## ❓ Open Questions

## 📝 Refinement Decisions
- Intent HM-LIGHT-LANE (DRI, round 1).
- Golden rows go through an exported JSON checked against the machine.yaml, not inlined rows (silent
  drift) and not `yaml.safe_load` (new user dependency) (DRI, round 1).
- Lever 1 takes all three: exact categories, approval in `spec_machine check`, compact `hm check` (DRI,
  round 1).
- PLAN gets an agent-judged short form, not removal; land and the Understanding block are unchanged
  (DRI, round 1).
- JSON lives at `specs/SPEC-<slug>.golden.json` (DRI, round 2).
- Compaction keeps the JSON line and collapses passing sections; `--full` restores (DRI, round 2).
- Bar pre-registered at <= 12.5x transcript ratio, the low end of the estimated $0.10-0.15/run saving;
  a miss means the lever estimate was wrong, and the rule is applied as written (DRI, round 2).
- `load_golden_table` stays for existing tests; an absent JSON is not a failure (agent, absent-case rule).
- spec-validator (one pass, MAJOR_REVISION, 11 critiques) applied before the stamp, none changing a DRI
  decision (agent): AC-009 now pins its rows in a fixture with the squash-alias check and runs on
  `bench.summarize` with its suspect, cap, leak, balance and model guards (critical x2); compaction
  keeps warning keys of passing sections (critical); `--full` = pre-change output plus the new keys;
  Step 5 reads the post-stamp state; JSON rows are the `{input, expected}` projection, superseded ACs
  excluded, unserialisable values refused; AC-003 bans import forms, not the substring; AC-010 lands
  the JSON; `hint` names `export-golden` on an absent JSON; per-target edit tool; AC-004 covers execute;
  AC-002 adds red-mode drift and absent rows. The published rows replace `results.jsonl`.
