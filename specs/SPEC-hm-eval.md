---
type: spec
task_slug: hm-eval
status: draft
created: 2026-10-14
tags: [harness-maker, spec, eval, code-quality, cost, hidden-tests, llm-judge]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
parent_spec: "[[SPEC-hm-light-lane-bench]]"
summary: "Turn the light-lane bench into an eval: plain vs /hm: on code quality first (hidden tests, lint/type deltas, a blind calibrated LLM rubric), cost second, published to docs/evals and the README"
---

# SPEC — hm-eval (plain prompt vs harness: code quality first, then cost)

## 🎯 Intent

The DRI wants one eval that shows, in numbers, how code written through the harness compares with
code written from a raw prompt, first on quality and then on what that quality costs. It has to be
easy to re-run after a harness change. Its results should live in `docs/`, and the README should
show the headline.

`scripts/bench_light_lane.py` (SPEC-hm-light-lane-bench) already runs both arms headlessly with the
same model and budget, grades hidden tests in isolation and prices every run. It measures one
thing, `hm_cost_ratio_small`, on five tasks that plain already solves 15/15. Both arms are at the
ceiling there, so those tasks cannot show a quality difference. This SPEC builds on that runner:
- a second task tier whose hidden tests are not saturated, with each test traceable to a sentence
  of its prompt;
- quality and token signals recorded per run;
- a blind, calibrated LLM rubric;
- a scorecard that leads with quality;
- a publish step that writes the scorecard into the docs.

The intent metric and its pre-registered verdict keep working, computed on tier 1 only.

The eval reports what comes out. If plain writes better code than `/hm:`, the docs say so.

## 🌅 Outcomes

- `INTEGRATION=1 uv run python scripts/bench_light_lane.py run [--tier 1|2|all]` runs both arms,
  grades them, scores quality, and by default makes one blind judge call per changed run. It ends
  by printing the scorecard.
- `uv run python scripts/bench_light_lane.py report --out DIR` reprints the scorecard offline. Its
  sections, in order:
  1. **Quality** (plain vs hm per tier)
  2. **Efficiency** (the cost of that quality)
  3. The existing **intent-metric** block, whose last line is still
     `hm_cost_ratio_small=<ratio|n/a>`
- `uv run python scripts/bench_light_lane.py publish --out DIR` is offline. It writes
  `docs/evals/RESULTS.md` and rewrites the README block between `<!-- hm:eval:start -->` and
  `<!-- hm:eval:end -->`: a small plain-vs-hm headline table with n in each cell, and a link. The
  trend is the git history of `RESULTS.md`, which names `bench_hash`, `harness_sha`, `runner_hash`
  and the tool versions.
- `docs/evals/README.md` (hand-written) explains:
  - what is measured and how to run it;
  - how to read the scorecard;
  - the direction table and the lead rule;
  - the fairness rules and the tier-2 sign-off;
  - the improvement loop: change the harness, re-run, publish, then read `git log -p
    docs/evals/RESULTS.md`.
- Tier 2: four new tasks (t6–t9) on the same `timeparse` fixture.
  - Each covers one change shape: a bug fix with a regression trap, a change that keeps an existing
    invariant, a stated multi-case contract, and a change with one source of truth.
  - Each ships a reference that passes every hidden test, and a damaged copy of the reference for
    judge calibration.
  - `check` proves the hidden tests discriminate.
  - Tier 1 (t1–t5) stays the cheap smoke and cost tier.
- Nothing in the unit suite calls a model or the network.

## 📋 In-Scope Scenarios

### S1: Every task's hidden tests discriminate
**Given** the task directories under `scripts/bench/tasks/`, each with a `tier` file (absent means
1) and an optional `seed/` overlay
**When** `check` runs
**Then** for every task:
- the starting tree is the fixture plus the seed;
- the hidden tests fail on the starting tree and pass on the reference, apart from the tests listed
  in `guards.txt`;
- guards are regression traps: they must pass on the starting tree and on the reference;
- the fixture's own visible tests pass on both;
- tier 2 holds 3–5 tasks, and each tier-2 task also ships a `damaged/` overlay (see S13).

### S2: Tokens are recorded per kind
**Given** a finished run
**When** the runner records it
**Then** the row carries `tokens: {input, output, cache_read, cache_write}`. Each is summed over the
run's own main and subagent transcript turns through `harness_maker.economics`, where `cache_write`
= 5m + 1h writes. The row also records `tier`.

### S3: A stall is distinguishable from a wrong fix
**Given** a graded run
**When** the runner classifies it
**Then** `outcome` is one of:
- `solved`: the hidden tests pass;
- `wrong`: a file under `timeparse/` or `tests/` changed, but the hidden tests fail. A change
  limited to `tests/` counts as changed;
- `stalled`: nothing under `timeparse/` or `tests/` changed, and the tests fail.

The change is measured against the task's starting tree (fixture plus seed) taken from the private
snapshot, not against git history. Changes to harness files, `specs/`, `work-docs/`, `.claude/` or
`CLAUDE.md` are not a change.

### S4: Deterministic quality checks read the source diff of changed runs only
**Given** a graded run whose outcome is not `stalled`
**When** quality is scored
**Then** the row's `quality` holds:
- `ruff_new`: new ruff errors in the changed `.py` files under `timeparse/` and `tests/`, i.e. the
  count on the final files minus the count on their starting versions. A new file starts at 0.
  Ruff runs `--isolated` with a rule set pinned in the runner;
- `mypy_new`: the same delta for `mypy --strict` on the package, run with an empty config from a
  clean copy;
- `diff_lines`: added plus removed lines in that scope;
- `tests_touched`: whether a file under `tests/` was added or changed;
- `regressions`: how many of the fixture's pristine visible tests (from the snapshot) fail against
  the final package.

These rules hold for every check:
- A config, `conftest.py` or `pyproject.toml` the agent left in the work dir is never read.
- The work dir is never modified.
- For a `stalled` run every signal is `null` with reason `stalled`.
- A check that cannot run records `null` with a reason and never changes `status`, `passed` or
  `outcome`.
- The ruff and mypy versions are recorded in the row (`quality_tools`) and folded into
  `runner_hash`.

### S5: The judge is blind
**Given** a run whose outcome is not `stalled`, with the judge enabled (the default; `--no-judge`
turns it off)
**When** the runner builds the judge input
**Then** the input (on stdin) holds only:
- the rubric `hm-eval-judge-v1` (below);
- the task prompt, without the `/hm:spec ` prefix;
- the source diff from S4's scope.

Before the diff is sent, these patterns are replaced with neutral tokens, and `judge.redactions`
records how many replacements were made:

| Pattern | Replaced with |
|---|---|
| `AC-\d+` | `REQ` |
| `SPEC-` | `DOC-` |
| `PLAN-` | `DOC-` |
| `/hm:` | `/x:` |
| `test_ac_\d+` | `test_req` |

The input never contains the arm, the run dir, the rep, or any harness, `specs/`, `work-docs/` or
`.claude/` content. Two runs whose diffs are equal after redaction therefore produce byte-identical
judge input, whichever arm they come from.

### S6: The judge call is isolated and accounted separately
**Given** a judge input
**When** the runner calls the judge
**Then** it makes exactly one call:
- `<claude-bin> -p --output-format json --tools "" --json-schema <RUBRIC_SCHEMA>`
- `--model <judge-model>`, where the judge model defaults to `--model`, the agent's model
- `--setting-sources project,local --strict-mcp-config`
- `--max-budget-usd <judge-budget>` (default 0.5)
- the cwd is an empty temp dir outside `--out`

Scores are `scope`, `clarity` and `maintainability`, each an integer from 1 to 5.

These cases are recorded, never imputed:
- A non-zero exit, a timeout, or output that breaks the schema records `judge.status: error` with
  null scores; these are counted.
- A missing judge cost is treated as 0 and counted as unpriced.

The judge cost is `judge.cost_usd`. It stays out of `cost_usd` and out of every arm mean, but counts
toward `--total-budget-usd`. The judge model, the rubric text, the judge argv and the redaction
table are part of `runner_hash`.

### S7: The scorecard leads with quality over balanced, changed runs
**Given** a results file
**When** `report` runs
**Then** for each tier it prints plain vs hm, in this order:
1. **Quality.** These lines:
   - runs;
   - hidden-test all-pass count;
   - hidden-case pass fraction;
   - solved / wrong / stalled counts;
   - mean `ruff_new`, `mypy_new` and `regressions`;
   - mean `diff_lines`;
   - `tests_touched` rate;
   - judge mean per criterion and overall.
2. **Efficiency:**
   - mean cost, mean tokens per kind, turns and wall time;
   - the hm/plain ratio of each;
   - the total judge cost, with the number of unpriced judge calls.
3. **The existing intent-metric block**, computed on tier-1 rows only and unchanged in rule and
   output.

Per-tier figures use only the task×arm cells that are complete (`runs_per_cell` usable rows) for
both arms. Excluded tasks are listed. Each quality mean is taken over the changed runs that carry
the signal, and its n is printed next to it, or `n/a (n=0)` when there are none. `--json` adds a
`scorecard` object beside the existing keys.

### S8: Lead labels follow a fixed direction table
**Given** a scorecard line
**When** it is labelled
**Then** the label is `hm`, `plain`, `tie`, `—` (no lead) or `n/a` (a side has n = 0). It comes
from this table, which lives once in the runner and once in `docs/evals/README.md`:

| Metric | Better | Lead rule |
|---|---|---|
| hidden all-pass count, solved count | higher | gap ≥ 2 runs, else `tie` |
| wrong count, stalled count | lower | gap ≥ 2 runs, else `tie` |
| hidden-case pass fraction | higher | gap ≥ 0.05, else `tie` |
| mean `ruff_new`, `mypy_new`, `regressions` | lower | exact compare |
| judge mean (each criterion, overall) | higher | gap ≥ 0.25, else `tie` |
| mean cost, tokens, turns, wall | lower | exact compare |
| `diff_lines`, `tests_touched` rate | none | always `—` |

Count lines compare equal-sized arms, because cells are balanced (S7). Nothing in the report or the
docs picks words by hand. A results set where plain is ahead prints `plain`. An arm whose runs
mostly stalled cannot win lint or regressions by having no code, because stalled runs carry null
quality (S4).

### S9: Publish writes RESULTS.md and the README block
**Given** a results dir
**When** `publish --out DIR` runs (`--docs`, default `docs/evals`; `--readme`, default `README.md`)
**Then** `RESULTS.md` holds the scorecard as Markdown tables, quality first, and names:
- `bench_hash`, `harness_sha` and `runner_hash`;
- the agent and judge models;
- the rubric id;
- the ruff and mypy versions;
- the tiers and runs per cell;
- the date range, taken from the rows' `started_at`.

The README block between the markers is replaced with a headline table and a link to
`docs/evals/RESULTS.md`. The table columns are plain | hm | lead, and each cell shows its n. The
rows are:
- tier-2 all-pass count;
- judge overall;
- new lint+type errors;
- regressions;
- tier-1 cost per run, with the ratio.

README bytes outside the markers are unchanged.

### S10: Publish is deterministic and idempotent
**Given** the same results dir
**When** `publish` runs twice, or runs on the same rows in another line order
**Then** `RESULTS.md` and the README are byte-identical each time. Rows are sorted by (tier, task,
arm, rep). The output holds no wall-clock time, absolute path or hostname.

### S11: Publish refuses what it cannot render honestly
**Given** any of:
- a README with zero marker pairs, several pairs, or an end marker before its start;
- a results file that mixes setups (the existing `MixedResultsError`);
- no usable rows;
- a tier whose task×arm cells are not complete for both arms.

**When** `publish` runs
**Then** it exits 2 with a message, before writing either file.

### S12: Results from before this SPEC still report and publish
**Given** rows in the 2026-10-14 schema (no `tier`, `tokens`, `outcome`, `quality`, `judge` or
`quality_tools`)
**When** `report` or `publish` runs
**Then**:
- the rows count as tier 1;
- the outcome is derived where it can be: `passed: true` → solved, otherwise `n/a`;
- every missing signal shows `n/a (n=0)`;
- the intent-metric block equals what the runner printed before this SPEC.

### S13: The judge is calibrated before tier-2 results count
**Given** every tier-2 task's reference overlay and its `damaged/` overlay: the reference with
planted defects (duplicated logic, dead code, a misleading name)
**When** `INTEGRATION=1 … canary --judge-calibration --record PATH` judges both diffs per task with
the real judge, or a test replays such a recording offline
**Then** the calibration passes only when, for every tier-2 task, `overall(reference) >
overall(damaged)`. The recording stores each judge input's hash, so a changed rubric, task or
redaction table makes it stale, and a stale recording does not pass.

### S14: Tier 2 needs DRI sign-off and a passing calibration before a live run
**Given** the tier-2 task dirs are committed
**When** `run --tier 2|all` starts
**Then** it exits 2 before any copy or spend unless both of these hold:
- `scripts/bench/tier2-signoff.json` names the current tier-2 hash (over the tier-2 task dirs) and
  the DRI who signed;
- `scripts/bench/judge-calibration.json` is a fresh, passing recording (S13).

`check` prints the tier-2 hash to sign.

Each tier-2 hidden test's docstring quotes, verbatim, the prompt sentence it follows from. A prompt
states every case its hidden tests check: no unstated edge case. The DRI's sign-off is the check
that the prompts are fair and do not lean towards either arm.

### S15: Fairness holds by construction
**Given** both arms of any task
**When** they run
**Then** SPEC-hm-light-lane-bench S3 still holds: same model, budget, turn cap, flags and fixture
bytes, differing only by the harness and the `/hm:spec ` prefix. Tier-2 prompts name no harness
step, stage, SPEC, PLAN or review. Task files are covered by `bench_hash`, which `RESULTS.md` shows,
so a task edited after its results shows up in the RESULTS.md diff.

## 🧑‍⚖️ Judge rubric (`rubric_id: hm-eval-judge-v1`)

The runner sends this text verbatim, followed by the task prompt and the redacted diff.

> You are reviewing a code change to a small Python library. You see the task its author was given
> and the diff of the source and test files. Score the change on three criteria, each an integer
> from 1 to 5. Judge only the code in the diff.
>
> Correctness is checked separately by tests. Do not score it, and do not guess whether tests pass.
>
> Do not reward length. A longer change, more comments, more tests or more files is not better in
> itself; a smaller change that does the job scores at least as well as a larger one.
>
> **scope**: does the change do what the task asks and nothing else?
> 5 = every edit serves the task; no unrelated edits, no speculative features.
> 3 = the task is addressed, with some unrelated or speculative edits.
> 1 = mostly unrelated edits, or the task's main change is missing.
>
> **clarity**: can a reader follow it?
> 5 = names say what things are; control flow is direct; comments only where the reason is not
> obvious.
> 3 = readable with effort; some vague names or needless indirection.
> 1 = hard to follow; misleading names, dead code or confusing flow.
>
> **maintainability**: will the next change be easy?
> 5 = one source of truth for each rule; fits the existing structure; no duplicated logic, no dead
> code.
> 3 = some duplication, or a structure that fights the existing code.
> 1 = logic copied in several places, or a change that works against the module's structure.
>
> Return JSON only: {"scope": n, "clarity": n, "maintainability": n, "note": "<at most 200
> characters>"}.

`overall` is the mean of the three. There is no `tests` criterion. It would reward the process
rather than the code, and correctness comes from the hidden tests.

## 🚫 Non-Goals

- Taking the live measurement. The DRI runs it after signing off tier 2 and recording the
  calibration. This SPEC delivers the instrument, the docs skeleton, and a seed `RESULTS.md`
  published from the 2026-10-14 tier-1 rows (quality `n/a`).
- The hm arm's stall after `/hm:spec` (6/15 on 2026-10-14). It is being fixed separately (PR #21).
  Until that lands, the eval shows it as `outcome: stalled`.
- A trend file (`history.jsonl`) or trend charts. Git history of `RESULTS.md` is the trend.
- Statistical tests or confidence intervals. n is printed and the tie bands are fixed.
- Pairwise (A/B) judging, judge ensembles, or re-judging old work dirs (a `score` backfill).
- A second fixture, other languages, Cursor/Codex arms.
- Changing the intent metric, its target or its verdict rule.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard |
| Location | `scripts/bench_light_lane.py` (one entry), task data under `scripts/bench/`, docs under `docs/evals/` | Smallest change; the approved bench SPEC's ACs and test ids keep their paths (PLAN ADR-001) |
| Live calls | `run` and `canary` refuse without `INTEGRATION=1`; `report`, `publish` and `check` are offline; unit tests keep the autouse failing `claude` stub, and the judge goes through `--claude-bin` like the agent | CLAUDE.md test policy |
| Budget | `--total-budget-usd` default raised from 40 to 80 | `--tier all` with the judge exceeds 40 |
| Dependencies | stdlib plus existing dev dependencies (ruff and mypy are already dev deps) | No new dependency |
| Pricing and tokens | `harness_maker.economics` only | One pricing authority |
| Judging quality | The LLM rubric judges quality; rule-based checks are limited to compiler-grade facts (lint/type error counts, line counts, test pass/fail) | CLAUDE.md LLM-judgment principle |
| Writes | `publish` renders both outputs first, then writes atomically (temp + rename), and touches only those two files | Implementation patterns |
| Boundaries | No edit under `src/harness_maker/templates/`, goldens, `step_sensitivity.py` or `CLAUDE.md` | Other HM-LIGHT-LANE stages edit those |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-002 | README marker contract: exactly one `<!-- hm:eval:start -->` / `<!-- hm:eval:end -->` pair in `README.md`. The content between them is owned by `publish`; bytes outside are never touched | public API/CLI contract | Once in the README, hand edits around it and every later publish rely on it. The name sits beside the `hm-doc-contract:*` markers without colliding with them |

IRR-001 (a `history.jsonl` schema) was dropped after spec-validator review. The id is kept so
review references stay valid. The judge rubric is not irreversible: it is covered by `runner_hash`
and the calibration hash, so changing it starts a new comparable series. The added `results.jsonl`
row fields are additive in a dev-only file whose readers tolerate their absence (S12).

## ✅ Verification Criteria

| Scenario | Verification mode | Test name |
|---|---|---|
| S1 | unit (subprocess pytest) | `tests/unit/test_bench_light_lane.py::test_hidden_tests_discriminate` (parametrized over every task dir), `test_tasks_ship_in_two_tiers` |
| S2 | unit (fake transcripts) | `test_tokens_are_summed_per_kind_over_main_and_subagent_turns` |
| S3 | unit (golden work dirs) | `test_outcome_tells_a_stall_from_a_wrong_fix` |
| S4 | unit (golden work dirs) | `test_quality_checks_count_new_errors_on_the_source_diff_only`, `test_tool_versions_enter_the_runner_hash` |
| S5 | unit (fake claude) | `test_judge_input_is_blind_to_the_arm` |
| S6 | unit (fake claude) | `test_judge_argv_is_isolated_and_schema_bound`, `test_judge_failure_is_recorded_not_imputed`, `test_judge_cost_stays_out_of_the_arm_cost`, `test_no_judge_and_stalled_runs_make_no_judge_call` |
| S7 | unit (golden rows) | `test_scorecard_leads_with_quality_over_balanced_changed_runs` |
| S7 (metric) | unit (property) | `test_intent_metric_ignores_tier_two_rows` |
| S8 | unit (golden rows) | `test_lead_labels_follow_the_direction_table` |
| S9 | unit (golden rows → golden files) | `test_publish_writes_results_and_readme_block` |
| S10 | unit (property) | `test_publish_is_idempotent_and_order_independent` |
| S11 | unit | `test_publish_refuses_bad_markers_mixed_empty_or_unbalanced_results` |
| S12 | unit (2026-10-14 rows) | `test_pre_eval_rows_report_and_publish_with_na` |
| S13 | unit (fake and recorded judge) | `test_judge_calibration_ranks_reference_above_damaged` |
| S14 | unit | `test_tier_two_run_needs_signoff_and_calibration`, `test_tier_two_hidden_tests_cite_their_prompt` |
| S15 | unit | `test_arms_differ_only_by_harness_and_prefix` (existing), `test_tier_two_prompts_name_no_harness_step` |
| Outcome (docs) | unit | `test_docs_readme_explains_every_scorecard_metric` |

### AC-001: Every task's hidden tests discriminate, and tier 2 ships 3–5 tasks
### AC-002: Rows record tokens per kind from the run's own transcripts
### AC-003: The outcome tells a stall from a wrong fix
### AC-004: Deterministic quality checks count new errors on the source diff of changed runs only
### AC-005: The judge input is blind to the arm, harness vocabulary redacted
### AC-006: The judge call is isolated, schema-bound and accounted separately
### AC-007: The scorecard leads with quality over balanced, changed runs
### AC-008: The intent metric is computed on tier-1 rows only
### AC-009: Lead labels follow the direction table
### AC-010: Publish writes RESULTS.md and the README block
### AC-011: Publish is idempotent and independent of row order
### AC-012: Publish refuses bad markers, mixed, empty or unbalanced results before writing
### AC-013: Pre-eval results still report and publish with n/a
### AC-014: Tier-2 prompts name no harness step
### AC-015: docs/evals/README.md explains every scorecard metric
### AC-016: The judge ranks every tier-2 reference above its damaged copy
### AC-017: A tier-2 live run needs DRI sign-off, a passing calibration and cited hidden tests

## ❓ Open Questions

- Residual length or self-preference bias. The judge is the agent's model family, and the rubric
  tells it not to reward length. The calibration (S13) checks only that the judge can rank planted
  defects. It does not check that a long, clean change and a short, clean one score alike. The first
  live `RESULTS.md` shows judge overall beside mean `diff_lines` per arm, so the DRI can see any
  correlation. No automatic correction is planned.
- `README.ko.md` gets no eval block, because the doc-contract test lets localized prose differ.
  Add one later if the DRI wants parity.

## 🔍 Refinement Decisions

- Interview not run. Scope comes from the DRI's two messages (2026-10-14):
  1. Formalise token efficiency, problem solving and code quality, keep the eval in the codebase,
     and publish it to docs and the README.
  2. Lead with how the harness's code quality compares to a raw prompt, add harder tasks, and make
     fairness an AC.
- **Three dimensions over one task suite:**
  - efficiency: tokens per kind, cost, turns, wall time, and hm/plain ratios;
  - problem solving: hidden all-pass, case fraction, and solved/wrong/stalled;
  - quality: ruff/mypy new-error deltas, regressions, diff size, tests touched, and the blind
    rubric.

  The judge is on by default (`--no-judge` turns it off). Its cost is reported separately and kept
  out of arm cost.
- **Quality is the headline**, per DRI message 2; efficiency is shown as the price of that quality.
- **Tier 2 is added**, which overrides the earlier "tasks stay five" default.
  - Four tasks on the existing fixture, with an optional per-task `seed/` overlay for the bug-fix
    task.
  - Tier 1 is unchanged and stays the only input to `hm_cost_ratio_small`.
- **The spec-validator review (12 findings, MAJOR_REVISION) is folded in:**
  1. Stalled runs carry null quality, and means are over changed runs with n printed.
  2. Harness vocabulary is redacted before judging.
  3. The rubric text is in this SPEC. The `tests` criterion is dropped, the rubric tells the judge
     not to reward length, and a calibration AC was added.
  4. A per-metric direction table was added.
  5. A DRI sign-off gate for tier 2 was added, plus prompt-cited hidden tests and no unstated edge
     cases.
  6. Per-tier figures use balanced cells only, publish refuses an unbalanced tier, and the default
     budget is now 80.
  7. `history.jsonl` and IRR-001 are dropped; the git history of `RESULTS.md` is the trend.
  8. The ruff and mypy versions are in `runner_hash` and `RESULTS.md`.
  9. The judge AC asserts exact flag/value pairs, and a null judge cost counts as 0.
  10. Count-based leads need a gap of at least 2 runs, and every headline cell shows its n.
  11. The seed is part of the starting tree, and a change limited to tests counts as changed.
  12. The judge model stays the agent model.
- Error checks count *new* errors against the task's starting files, so a fixture blemish never
  counts against either arm. The fixture is ruff- and `mypy --strict`-clean today (checked
  2026-10-14).
- Commands are `run`, `report` and `publish` (plus the existing `check` and `canary`), on the
  existing script rather than a renamed `scripts/eval.py` (PLAN ADR-001).
- Lane `full`: about fifteen files plus four task dirs, and one irreversible decision.
